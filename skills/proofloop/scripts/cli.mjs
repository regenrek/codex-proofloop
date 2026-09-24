#!/usr/bin/env node
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  realpathSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { join, relative, resolve } from "node:path";
import { parseArgs } from "node:util";
import { matches, requireThat, validatePolicy } from "./policy.mjs";
import {
  changedPaths,
  digest,
  ensureArtifact,
  git,
  inside,
  isSensitive,
  readJSON,
  sha,
  snapshot,
  writeJSON,
} from "./workspace.mjs";
const runner = digest(
  ["cli.mjs", "policy.mjs", "workspace.mjs"].map((p) =>
    sha(readFileSync(new URL(p, import.meta.url))),
  ),
);
const help = `Proofloop — record checks against an exact Git working state (Node 24+)

  proofloop start  --project PATH --id ID [--policy proofloop.json]
  proofloop run    --project PATH --id ID
  proofloop status --project PATH --id ID
  proofloop finish --project PATH --id ID [--review .proofloop/review.json]

start freezes one policy and the existing working state. run executes every configured
check in sequence, in fresh output directories. status/finish recompute freshness.
finish exits 0 only when all checks, artifacts, scope and required review are satisfied.
Exit codes: 0 success, 2 incomplete/rejected, 1 invocation/runtime error.
Commands are argv arrays, without a shell. No background agent or model is started.
`;
const print = (value) => {
  process.stdout.write(JSON.stringify(value, null, 2) + "\n");
};
function report(stdout, kind) {
  if (kind === "node-tap") {
    const count = (name) => {
      const found = [...stdout.matchAll(new RegExp(`^# ${name} (\\d+)\\s*$`, "gm"))];
      requireThat(found.length === 1, `Missing/ambiguous TAP ${name}`);
      return Number(found[0][1]);
    };
    const tests = count("tests");
    requireThat(
      tests > 0 &&
        count("pass") === tests &&
        ["fail", "cancelled", "skipped", "todo"].every((n) => count(n) === 0),
      "Incomplete TAP execution",
    );
    requireThat(
      stdout.startsWith("TAP version 13") && /^1\.\.\d+$/m.test(stdout),
      "Not a complete TAP report",
    );
    return tests;
  }
  const parsed = JSON.parse(stdout);
  const stats = parsed.stats;
  requireThat(
    stats &&
      Array.isArray(parsed.suites) &&
      parsed.suites.length > 0 &&
      Array.isArray(parsed.errors) &&
      parsed.errors.length === 0,
    "Missing Playwright results",
  );
  requireThat(
    Number.isInteger(stats.expected) &&
      Number(stats.expected) > 0 &&
      ["unexpected", "flaky", "skipped"].every((k) => stats[k] === 0),
    "Incomplete Playwright execution",
  );
  return Number(stats.expected);
}
function policyProblems(base, current) {
  const problems = [];
  const hash = sha(readFileSync(inside(base.root, base.policyPath)));
  if (hash !== base.policyHash) {
    problems.push("POLICY_CHANGED: start a new run after deliberate policy changes");
  }
  for (const path of changedPaths(base.snapshot, current)) {
    if (isSensitive(path) || !base.policy.allowedPaths.some((p) => matches(path, p))) {
      problems.push(`OUT_OF_SCOPE: ${path}`);
    }
    if (base.policy.testPatterns.some((p) => matches(path, p))) {
      const action = !base.snapshot.files[path]
        ? "add"
        : !current.files[path]
          ? "delete"
          : "modify";
      if (!base.policy.testChanges.some((c) => c.path === path && c.action === action)) {
        problems.push(`UNPLANNED_TEST_CHANGE: ${action} ${path}`);
      }
    }
  }
  return problems;
}
async function execute(root, folder, check, before) {
  const attempt = randomUUID();
  const out = inside(folder, `checks/${check.id}/${attempt}`);
  mkdirSync(out, { recursive: true, mode: 0o700 });
  const stdoutPath = join(out, "stdout.log");
  const stderrPath = join(out, "stderr.log");
  const stdoutFD = openSync(stdoutPath, "wx", 0o600);
  const stderrFD = openSync(stderrPath, "wx", 0o600);
  const result = {
    id: check.id,
    attempt,
    candidate: before.fingerprint,
    after: "",
    command: check.command,
    cwd: check.cwd,
    startedAt: new Date().toISOString(),
    finishedAt: "",
    exitCode: null,
    signal: null,
    timedOut: false,
    tests: 0,
    passed: false,
    problems: [],
    artifacts: [],
    node: process.version,
    platform: process.platform,
    runner,
  };
  const cwd = inside(root, check.cwd);
  requireThat(statSync(cwd).isDirectory(), "Check cwd must be a directory");
  // Reporters must use stdout. Other artifacts use the fresh directory supplied below.
  const env = {
    ...process.env,
    PROOFLOOP_OUTPUT_DIR: out,
    PROOFLOOP_RUN_ID: folder.split("/").at(-1),
  };
  delete env.NODE_TEST_CONTEXT;
  delete env.PLAYWRIGHT_JSON_OUTPUT_FILE;
  delete env.PLAYWRIGHT_JSON_OUTPUT_DIR;
  delete env.PLAYWRIGHT_JSON_OUTPUT_NAME;
  let interrupted = false;
  try {
    await new Promise((done) => {
      const child = spawn(check.command[0], check.command.slice(1), {
        cwd,
        env,
        shell: false,
        detached: process.platform !== "win32",
        stdio: ["ignore", stdoutFD, stderrFD],
      });
      const stop = () => {
        if (!child.pid) {
          return;
        }
        try {
          if (process.platform === "win32") {
            child.kill("SIGKILL");
          } else {
            process.kill(-child.pid, "SIGKILL");
          }
        } catch {
          /* Already exited. */
        }
      };
      const interrupt = () => {
        interrupted = true;
        stop();
      };
      process.once("SIGINT", interrupt);
      process.once("SIGTERM", interrupt);
      const timeout = setTimeout(() => {
        result.timedOut = true;
        stop();
      }, check.timeoutSeconds * 1000);
      child.once("error", (error) => {
        result.problems.push(`SPAWN_FAILED: ${error.message}`);
      });
      child.once("close", (code, signal) => {
        clearTimeout(timeout);
        stop();
        process.removeListener("SIGINT", interrupt);
        process.removeListener("SIGTERM", interrupt);
        result.exitCode = code;
        result.signal = signal;
        done();
      });
    });
  } finally {
    closeSync(stdoutFD);
    closeSync(stderrFD);
  }
  if (interrupted) {
    result.problems.push("INTERRUPTED");
  }
  if (result.timedOut) {
    result.problems.push("TIMEOUT");
  }
  if (result.exitCode !== 0 || result.signal) {
    result.problems.push("CHECK_FAILED");
  }
  try {
    requireThat(statSync(stdoutPath).size <= 20 * 1024 * 1024, "Report exceeds 20 MiB");
    result.tests = report(readFileSync(stdoutPath, "utf8"), check.reporter);
  } catch (error) {
    result.problems.push(`REPORT_INVALID: ${String(error)}`);
  }
  for (const artifact of check.artifacts) {
    try {
      requireThat(artifact !== "stdout.log" && artifact !== "stderr.log", "Reserved artifact name");
      const full = inside(out, artifact);
      result.artifacts.push({
        path: relative(root, full).split("\\").join("/"),
        sha256: ensureArtifact(full),
      });
    } catch {
      result.problems.push(`ARTIFACT_MISSING: ${artifact}`);
    }
  }
  for (const path of [stdoutPath, stderrPath]) {
    result.artifacts.push({
      path: relative(root, path).split("\\").join("/"),
      sha256: ensureArtifact(path, false),
      log: true,
    });
  }
  result.after = snapshot(root).fingerprint;
  if (result.after !== before.fingerprint) {
    result.problems.push("INPUT_CHANGED_DURING_CHECK");
  }
  result.finishedAt = new Date().toISOString();
  result.passed = result.problems.length === 0;
  writeJSON(inside(folder, `checks/${check.id}/${attempt}.json`), result);
  return result;
}
async function main() {
  const { values, positionals } = parseArgs({
    options: {
      project: { type: "string" },
      id: { type: "string" },
      policy: { type: "string" },
      review: { type: "string" },
      help: { type: "boolean", short: "h" },
    },
    allowPositionals: true,
    strict: true,
  });
  if (values.help || positionals.length === 0) {
    process.stdout.write(help);
    return;
  }
  const command = positionals[0];
  requireThat(
    positionals.length === 1 && ["start", "run", "status", "finish"].includes(command),
    "Unknown command; use --help",
  );
  requireThat(values.id && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(values.id), "Invalid run ID");
  requireThat(!values.policy || command === "start", "--policy belongs to start");
  requireThat(!values.review || command === "finish", "--review belongs to finish");
  const root = realpathSync(resolve(values.project ?? "."));
  requireThat(
    realpathSync(git(root, "rev-parse", "--show-toplevel").trim()) === root,
    "Use the Git worktree root as --project",
  );
  // Gitignore controls source/build separation; generated evidence must not enter its own fingerprint.
  try {
    git(root, "check-ignore", "-q", "--no-index", ".proofloop/ignore-probe");
  } catch {
    throw new Error("Add .proofloop/ to the root .gitignore before starting");
  }
  requireThat(
    git(root, "ls-files", "--", ".proofloop").trim() === "",
    "Evidence must not be tracked",
  );
  const runs = inside(root, ".proofloop/runs");
  mkdirSync(runs, { recursive: true, mode: 0o700 });
  const folder = inside(runs, values.id);
  const lock = inside(root, ".proofloop/runner.lock");
  const mutating = command !== "status";
  let lockFD;
  if (mutating) {
    try {
      lockFD = openSync(lock, "wx", 0o600);
      writeFileSync(lockFD, `${process.pid}\n`);
    } catch {
      throw new Error(
        "RUN_BUSY: .proofloop/runner.lock exists; confirm its process has ended before removing a stale lock",
      );
    }
  } else {
    requireThat(!existsSync(lock), "RUN_BUSY");
  }
  try {
    if (command === "start") {
      requireThat(!existsSync(folder), "RUN_EXISTS: choose a new run ID");
      const policyPath = values.policy ?? "proofloop.json";
      const path = inside(root, policyPath);
      requireThat(
        !policyPath.startsWith(".proofloop/") && !isSensitive(policyPath),
        "Policy must be a non-secret source file",
      );
      const policy = validatePolicy(readJSON(path));
      const base = {
        root,
        policyPath,
        policyHash: sha(readFileSync(path)),
        policy,
        snapshot: snapshot(root),
        createdAt: new Date().toISOString(),
      };
      requireThat(base.snapshot.files[policyPath], "Policy must be tracked or nonignored");
      mkdirSync(folder, { mode: 0o700 });
      writeJSON(join(folder, "baseline.json"), base);
      print({
        status: "started",
        id: values.id,
        candidate: base.snapshot.fingerprint,
        policy: policyPath,
        directory: folder,
      });
      return;
    }
    const base = readJSON(inside(folder, "baseline.json"));
    requireThat(base.root === root, "Run belongs to a different checkout");
    validatePolicy(base.policy);
    const current = snapshot(root);
    const problems = policyProblems(base, current);
    const resultPath = inside(folder, "execution.json");
    if (command === "run") {
      requireThat(problems.length === 0, problems.join("\n"));
      const execution = {
        candidate: current.fingerprint,
        checks: [],
        startedAt: new Date().toISOString(),
      };
      // Invalidate the previous attempt before spawning; a crash cannot expose an old success.
      writeJSON(resultPath, execution);
      for (const check of base.policy.checks) {
        requireThat(
          snapshot(root).fingerprint === current.fingerprint,
          "INPUT_CHANGED_DURING_CHECK",
        );
        const result = await execute(root, folder, check, current);
        execution.checks.push(result);
        writeJSON(resultPath, execution);
        if (!result.passed) {
          break;
        }
      }
      const passed =
        execution.checks.length === base.policy.checks.length &&
        execution.checks.every((c) => c.passed);
      print({ status: passed ? "checks-passed" : "failed", ...execution });
      process.exitCode = passed ? 0 : 2;
      return;
    }
    const execution = existsSync(resultPath) ? readJSON(resultPath) : null;
    if (!execution) {
      problems.push("EXECUTION_REQUIRED");
    } else {
      if (execution.candidate !== current.fingerprint) {
        problems.push("STALE: candidate differs from executed state");
      }
      for (const check of base.policy.checks) {
        const result = execution.checks.find((c) => c.id === check.id);
        if (!result) {
          problems.push(`EXECUTION_REQUIRED: ${check.id}`);
          continue;
        }
        if (!result.passed || result.exitCode !== 0 || result.timedOut || result.tests <= 0) {
          problems.push(`CHECK_FAILED: ${check.id}`, ...result.problems);
        }
        if (
          result.candidate !== current.fingerprint ||
          result.after !== current.fingerprint ||
          result.runner !== runner
        ) {
          problems.push(`STALE: ${check.id}`);
        }
        if (digest(result.command) !== digest(check.command)) {
          problems.push(`COMMAND_CHANGED: ${check.id}`);
        }
        for (const artifact of result.artifacts) {
          try {
            requireThat(
              ensureArtifact(inside(root, artifact.path), !artifact.log) === artifact.sha256,
              "changed",
            );
          } catch {
            problems.push(`ARTIFACT_CHANGED: ${artifact.path}`);
          }
        }
      }
    }
    const evidence = digest({
      policyHash: base.policyHash,
      baseline: base.snapshot.fingerprint,
      candidate: current.fingerprint,
      execution,
    });
    let review = null;
    if (base.policy.review) {
      const storedReview = inside(folder, "review.json");
      if (!values.review && !existsSync(storedReview)) {
        problems.push("REVIEW_REQUIRED");
      } else {
        review = readJSON(values.review ? inside(root, values.review) : storedReview);
        const r = review;
        if (
          r.threadId !== base.policy.review.threadId ||
          r.evidence !== evidence ||
          r.verdict !== "pass" ||
          !Array.isArray(r.criteria) ||
          !base.policy.criteria.every((c) => r.criteria.includes(c.id)) ||
          !Array.isArray(r.findings) ||
          r.findings.length !== 0 ||
          typeof r.summary !== "string" ||
          !r.summary.trim()
        ) {
          problems.push("REVIEW_INVALID");
        }
      }
    } else {
      requireThat(!values.review, "Review must be assigned in the policy before start");
    }
    const result = {
      status: problems.length ? "incomplete" : "verified",
      id: values.id,
      evidence,
      candidate: current.fingerprint,
      goal: base.policy.goal,
      environment: base.policy.environment,
      criteria: base.policy.criteria,
      changedPaths: changedPaths(base.snapshot, current),
      problems,
      checks: execution?.checks ?? [],
      review: {
        required: Boolean(base.policy.review),
        assignment: base.policy.review,
        attestation: review,
        authenticated: false,
      },
      directory: folder,
    };
    if (command === "finish") {
      if (!problems.length && review) {
        writeJSON(join(folder, "review.json"), review);
      }
      writeJSON(join(folder, "finish.json"), result);
    }
    print(result);
    process.exitCode = problems.length ? 2 : 0;
  } finally {
    if (lockFD !== undefined) {
      closeSync(lockFD);
      rmSync(lock);
    }
  }
}
main().catch((error) => {
  print({ status: "error", error: String(error instanceof Error ? error.message : error) });
  process.exitCode = 1;
});
