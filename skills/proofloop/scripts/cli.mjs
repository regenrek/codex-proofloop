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
  checkInputs,
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
const version = JSON.parse(
  readFileSync(new URL("../version.json", import.meta.url), "utf8"),
).version;
const runner = digest(
  ["cli.mjs", "policy.mjs", "workspace.mjs", "../version.json"].map((p) =>
    sha(readFileSync(new URL(p, import.meta.url))),
  ),
);
const help = `Proofloop — record checks against an exact Git working state (Node 24+)

  proofloop --version
  proofloop start  --project PATH --id ID [--policy proofloop.json]
  proofloop run    --project PATH --id ID
  proofloop status --project PATH --id ID
  proofloop finish --project PATH --id ID [--review .proofloop/review.json]

start freezes one policy and the existing working state. run executes every configured
check in sequence, in fresh output directories. status/finish recompute freshness.
finish exits 0 only when all checks, artifacts, scope and required review are satisfied.
Exit codes: 0 success, 2 incomplete/rejected, 1 invocation/runtime error.
Add --compact for short output with a full record path.
Commands are argv arrays, without a shell. No background agent or model is started.
`;
const print = (value) => {
  process.stdout.write(JSON.stringify(value, null, 2) + "\n");
};
function report(stdout, kind) {
  const outcome = (tests, complete) => ({
    tests,
    problems: complete && tests > 0 ? [] : ["TESTS_INCOMPLETE"],
  });
  if (kind === "node-tap") {
    const count = (name) => {
      const found = [...stdout.matchAll(new RegExp(`^# ${name} (\\d+)\\s*$`, "gm"))];
      requireThat(found.length === 1, `Missing/ambiguous TAP ${name}`);
      const value = Number(found[0][1]);
      requireThat(Number.isSafeInteger(value), `Invalid TAP ${name}`);
      return value;
    };
    const tests = count("tests");
    const passed = count("pass");
    const other = ["fail", "cancelled", "skipped", "todo"].map(count);
    requireThat(
      stdout.startsWith("TAP version 13") && /^1\.\.\d+$/m.test(stdout),
      "Not a complete TAP report",
    );
    return outcome(tests, passed === tests && other.every((n) => n === 0));
  }
  const parsed = JSON.parse(stdout);
  requireThat(parsed !== null && typeof parsed === "object", "Expected a JSON report");
  const count = (value) => {
    requireThat(Number.isSafeInteger(value) && Number(value) >= 0, "Invalid report count");
    return Number(value);
  };
  if (kind === "vitest-json") {
    const tests = count(parsed.numTotalTests);
    const passed = count(parsed.numPassedTests);
    const other = [
      "numFailedTests",
      "numPendingTests",
      "numTodoTests",
      "numFailedTestSuites",
      "numPendingTestSuites",
    ].map((key) => count(parsed[key]));
    requireThat(
      typeof parsed.success === "boolean" && Array.isArray(parsed.testResults),
      "Missing Vitest results",
    );
    const suites = parsed.testResults;
    requireThat(
      suites.every((s) => s && Array.isArray(s.assertionResults)),
      "Invalid Vitest suites",
    );
    const assertions = suites.flatMap((s) => s.assertionResults);
    requireThat(assertions.length === tests, "Vitest count does not match assertions");
    return outcome(
      tests,
      parsed.success &&
        passed === tests &&
        other.every((n) => n === 0) &&
        suites.every((s) => s.status === "passed") &&
        assertions.every((a) => a.status === "passed"),
    );
  }
  const stats = parsed.stats;
  requireThat(
    stats && Array.isArray(parsed.suites) && Array.isArray(parsed.errors),
    "Missing Playwright results",
  );
  const expected = count(stats.expected);
  const unexpected = count(stats.unexpected);
  const flaky = count(stats.flaky);
  const skipped = count(stats.skipped);
  return outcome(
    expected + unexpected + flaky + skipped,
    expected > 0 &&
      unexpected === 0 &&
      flaky === 0 &&
      skipped === 0 &&
      parsed.suites.length > 0 &&
      parsed.errors.length === 0,
  );
}
function printExecution(execution, status, record, compact) {
  print(
    compact
      ? {
          status,
          candidate: execution.candidate,
          record,
          checks: execution.checks.map(({ id, passed, tests, problems }) => ({
            id,
            passed,
            tests,
            problems,
          })),
        }
      : { status, ...execution },
  );
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
async function execute(root, folder, check, before, inputs) {
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
    inputs,
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
  if (check.reporter !== "exit-code") {
    try {
      requireThat(statSync(stdoutPath).size <= 20 * 1024 * 1024, "Report exceeds 20 MiB");
      const parsed = report(readFileSync(stdoutPath, "utf8"), check.reporter);
      result.tests = parsed.tests;
      result.problems.push(...parsed.problems);
    } catch (error) {
      result.problems.push(`REPORT_INVALID: ${String(error)}`);
    }
  }
  for (const artifact of check.artifacts) {
    try {
      requireThat(artifact !== "stdout.log" && artifact !== "stderr.log", "Reserved artifact name");
      const full = inside(out, artifact);
      if (existsSync(full) && statSync(full).isFile() && statSync(full).size === 0) {
        result.problems.push(`ARTIFACT_EMPTY: ${artifact}`);
        continue;
      }
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
  try {
    if (digest(checkInputs(root, check)) !== digest(inputs)) {
      result.problems.push("INPUT_CHANGED_DURING_CHECK");
    }
  } catch (error) {
    result.problems.push(`INPUT_CHANGED_DURING_CHECK: ${String(error)}`);
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
      compact: { type: "boolean" },
      version: { type: "boolean" },
      help: { type: "boolean", short: "h" },
    },
    allowPositionals: true,
    strict: true,
  });
  if (values.version) {
    process.stdout.write(version + "\n");
    return;
  }
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
      for (const check of policy.checks) {
        checkInputs(root, check);
      }
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
      const inputs = base.policy.checks.map((check) => checkInputs(root, check));
      for (const [index, check] of base.policy.checks.entries()) {
        requireThat(
          snapshot(root).fingerprint === current.fingerprint,
          "INPUT_CHANGED_DURING_CHECK",
        );
        requireThat(
          digest(checkInputs(root, check)) === digest(inputs[index]),
          "INPUT_CHANGED_DURING_CHECK",
        );
        const result = await execute(root, folder, check, current, inputs[index]);
        execution.checks.push(result);
        writeJSON(resultPath, execution);
        if (!result.passed) {
          break;
        }
      }
      const passed =
        execution.checks.length === base.policy.checks.length &&
        execution.checks.every((c) => c.passed);
      printExecution(
        execution,
        passed ? "checks-passed" : "failed",
        resultPath,
        Boolean(values.compact),
      );
      process.exitCode = passed ? 0 : 2;
      return;
    }
    const execution = existsSync(resultPath) ? readJSON(resultPath) : null;
    const currentInputs = {};
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
        try {
          currentInputs[check.id] = checkInputs(root, check);
          if (digest(currentInputs[check.id]) !== digest(result.inputs)) {
            problems.push(`INPUT_CHANGED: ${check.id}`);
          }
        } catch (error) {
          currentInputs[check.id] = { error: String(error) };
          problems.push(`INPUT_CHANGED: ${check.id}: ${String(error)}`);
        }
        if (
          !result.passed ||
          result.exitCode !== 0 ||
          result.signal ||
          result.timedOut ||
          (check.reporter !== "exit-code" && result.tests <= 0)
        ) {
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
      currentInputs,
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
    const record = join(folder, command === "finish" ? "finish.json" : "status.json");
    if (command === "status") {
      writeJSON(record, result);
    }
    print(
      values.compact
        ? {
            status: result.status,
            id: result.id,
            candidate: result.candidate,
            evidence: result.evidence,
            problems: result.problems,
            record,
            checks: result.checks.map(({ id, passed, tests, problems }) => ({
              id,
              passed,
              tests,
              problems,
            })),
            reviewRequired: result.review.required,
          }
        : result,
    );
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
