// Public CLI acceptance: actual processes, temporary Git repositories, no helper mocks.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
const repo = fileURLToPath(new URL("../", import.meta.url));
const cli = resolve(repo, "skills/proofloop/scripts/cli.mjs");
const results = [];
const output = process.env.PROOFLOOP_OUTPUT_DIR ?? resolve(repo, ".proofloop/acceptance");
mkdirSync(output, { recursive: true });
const fixtureCode = `import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
test('public outcome', () => {
  assert.equal(readFileSync('src/value.txt', 'utf8').trim(), '2');
  writeFileSync(join(process.env.PROOFLOOP_OUTPUT_DIR, 'result.json'), JSON.stringify({ observed: 2 }));
});
`;
function fixture(options = {}) {
  const root = mkdtempSync(join(tmpdir(), "proofloop acceptance "));
  const write = (name, content) => {
    mkdirSync(resolve(root, name, ".."), { recursive: true });
    writeFileSync(
      join(root, name),
      typeof content === "string" ? content : JSON.stringify(content, null, 2),
    );
  };
  const git = (...args) => {
    const p = spawnSync("git", args, { cwd: root, encoding: "utf8" });
    assert.equal(p.status, 0, p.stderr);
    return p.stdout;
  };
  write(".gitignore", ".proofloop/\n");
  write("src/value.txt", "1\n");
  write("tests/journey.test.mjs", fixtureCode);
  write("tests/old.test.mjs", "// retirement candidate\n");
  const policy = {
    goal: "The public outcome is 2",
    allowedPaths: ["src/**", "tests/**"],
    testPatterns: ["**/*.test.*"],
    criteria: [
      { id: "outcome", behavior: "Read value 2", failures: ["Wrong value", "No execution"] },
    ],
    checks: [
      {
        id: "journey",
        criteria: ["outcome"],
        command: [process.execPath, "--test", "--test-reporter=tap", "tests/journey.test.mjs"],
        cwd: ".",
        timeoutSeconds: 10,
        reporter: "node-tap",
        artifacts: ["result.json"],
      },
    ],
    testChanges: [],
    environment: { target: "local fixture", seed: "value-2" },
    review: null,
    ...options,
  };
  write("proofloop.json", policy);
  git("init", "-q");
  git("config", "user.email", "fixture@example.invalid");
  git("config", "user.name", "Fixture");
  git("add", ".");
  git("commit", "-qm", "baseline");
  function call(command, ...args) {
    const p = spawnSync(
      process.execPath,
      [cli, command, "--project", root, "--id", "pilot", ...args],
      { encoding: "utf8", timeout: 20000 },
    );
    assert.equal(p.signal, null, p.stderr);
    let body;
    try {
      body = JSON.parse(p.stdout);
    } catch {
      throw Error(`${command}: ${p.stdout}\n${p.stderr}`);
    }
    return { code: p.status, body };
  }
  const good = (command, ...args) => {
    const r = call(command, ...args);
    assert.equal(r.code, 0, JSON.stringify(r.body));
    return r.body;
  };
  return {
    root,
    write,
    git,
    policy,
    call,
    good,
    cleanup: () => rmSync(root, { recursive: true, force: true }),
  };
}
async function scenario(name, options, run) {
  const f = fixture(options);
  const started = Date.now();
  try {
    await run(f);
    results.push({ name, passed: true, durationMs: Date.now() - started });
  } catch (error) {
    results.push({ name, passed: false, error: String(error) });
  } finally {
    f.cleanup();
  }
}
const start = (f) => {
  f.good("start");
  f.write("src/value.txt", "2\n");
};
const rejects = (f, command, reason, ...args) => {
  const r = f.call(command, ...args);
  assert.notEqual(r.code, 0, JSON.stringify(r.body));
  assert.ok(JSON.stringify(r.body).includes(reason), JSON.stringify(r.body));
  return r.body;
};
await scenario("real execution and fresh artifact finish", {}, (f) => {
  start(f);
  f.good("run");
  const result = f.good("finish");
  assert.equal(result.status, "verified");
  assert.deepEqual(result.changedPaths, ["src/value.txt"]);
});
await scenario("committed changes remain visible and unplanned tests block", {}, (f) => {
  start(f);
  f.write("tests/new.test.mjs", "export {};");
  f.git("add", ".");
  f.git("commit", "-qm", "during run");
  rejects(f, "finish", "UNPLANNED_TEST_CHANGE");
});
await scenario("preexisting dirty content preserved", {}, (f) => {
  f.write("src/value.txt", "2\n");
  f.good("start");
  f.good("run");
  assert.deepEqual(f.good("finish").changedPaths, []);
  f.write("src/value.txt", "3\n");
  rejects(f, "finish", "STALE");
});
await scenario("policy cannot widen scope or detection", {}, (f) => {
  start(f);
  f.policy.allowedPaths = ["**"];
  f.policy.testPatterns = [];
  f.write("proofloop.json", f.policy);
  rejects(f, "run", "POLICY_CHANGED");
});
await scenario("outside-scope changes block even after commit", {}, (f) => {
  start(f);
  f.write("other.txt", "outside");
  f.git("add", ".");
  f.git("commit", "-qm", "outside");
  rejects(f, "run", "OUT_OF_SCOPE");
});
await scenario("actual assertion failure and failed retry invalidate success", {}, (f) => {
  start(f);
  f.good("run");
  f.write("src/value.txt", "3\n");
  const failed = rejects(f, "run", "CHECK_FAILED");
  assert.equal(failed.checks[0].tests, 1);
  assert.ok(!failed.checks[0].problems.some((p) => p.startsWith("REPORT_INVALID")));
  f.write("src/value.txt", "2\n");
  rejects(f, "finish", "CHECK_FAILED");
});
for (const [name, code, reason] of [
  [
    "zero tests",
    "console.log('TAP version 13\\n1..0\\n# tests 0\\n# pass 0\\n# fail 0\\n# cancelled 0\\n# skipped 0\\n# todo 0')",
    "TESTS_INCOMPLETE",
  ],
  ["exit-only fake evidence", "console.log(JSON.stringify({ok:true}))", "REPORT_INVALID"],
  ["nonzero exit", "process.exit(23)", "CHECK_FAILED"],
  ["timeout", "setInterval(()=>{},1000)", "TIMEOUT"],
]) {
  await scenario(
    name,
    {
      checks: [
        {
          id: "journey",
          criteria: ["outcome"],
          command: [process.execPath, "-e", code],
          cwd: ".",
          timeoutSeconds: 1,
          reporter: "node-tap",
          artifacts: [],
        },
      ],
    },
    (f) => {
      start(f);
      rejects(f, "run", reason);
      rejects(f, "finish", reason);
    },
  );
}
await scenario("skipped real tests cannot finish", {}, (f) => {
  f.write(
    "tests/journey.test.mjs",
    "import test from 'node:test'; test.skip('not executed',()=>{});",
  );
  start(f);
  rejects(f, "run", "TESTS_INCOMPLETE");
});
await scenario("missing new artifact cannot reuse earlier artifact", {}, (f) => {
  f.write("tests/journey.test.mjs", "import test from 'node:test'; test('runs',()=>{});");
  start(f);
  rejects(f, "run", "ARTIFACT_MISSING");
});
await scenario("untracked input and staged changes invalidate evidence", {}, (f) => {
  start(f);
  f.good("run");
  f.write("src/new.txt", "input");
  rejects(f, "finish", "STALE");
  rmSync(join(f.root, "src/new.txt"));
  f.good("finish");
  f.git("add", "src/value.txt");
  rejects(f, "finish", "STALE");
});
await scenario("artifact tampering invalidates evidence", {}, (f) => {
  start(f);
  const run = f.good("run");
  f.write(run.checks[0].artifacts[0].path, "changed evidence");
  rejects(f, "finish", "ARTIFACT_CHANGED");
});
await scenario(
  "planned retirement supported, unplanned rename rejected",
  {
    testChanges: [
      {
        path: "tests/old.test.mjs",
        action: "delete",
        reason: "No observable behavior; real journey covers outcome",
        checks: ["journey"],
      },
    ],
  },
  (f) => {
    start(f);
    rmSync(join(f.root, "tests/old.test.mjs"));
    f.good("run");
    f.good("finish");
    f.write("tests/renamed.test.mjs", fixtureCode);
    rejects(f, "finish", "UNPLANNED_TEST_CHANGE");
  },
);
await scenario(
  "review is required and tied to exact evidence",
  { review: { threadId: "checker-task", model: "gpt-6-luna", reasoning: "max" } },
  (f) => {
    start(f);
    f.good("run");
    const pending = rejects(f, "finish", "REVIEW_REQUIRED");
    const review = {
      threadId: "checker-task",
      evidence: pending.evidence,
      verdict: "pass",
      criteria: ["outcome"],
      findings: [],
      summary: "Observed outcome through recorded CLI execution.",
    };
    const statusPath = join(f.root, ".proofloop/runs/pilot/status.json");
    const finishPath = join(f.root, ".proofloop/runs/pilot/finish.json");
    const sameSnapshot = (result) => {
      assert.deepEqual(JSON.parse(readFileSync(statusPath, "utf8")), result);
      assert.deepEqual(JSON.parse(readFileSync(finishPath, "utf8")), result);
    };
    for (const invalid of [
      null,
      "{broken",
      { ...review, threadId: "wrong" },
      { ...review, evidence: "old" },
      { ...review, verdict: "unknown" },
    ]) {
      f.write(".proofloop/review.json", invalid);
      sameSnapshot(rejects(f, "finish", "REVIEW_INVALID", "--review", ".proofloop/review.json"));
    }
    f.write(".proofloop/review.json", {
      ...review,
      verdict: "fail",
      findings: ["Public journey loses state"],
    });
    sameSnapshot(rejects(f, "finish", "REVIEW_REJECTED", "--review", ".proofloop/review.json"));
    rejects(f, "status", "REVIEW_REJECTED");
    f.write(".proofloop/review.json", { ...review, findings: ["Still open"] });
    rejects(f, "finish", "REVIEW_REJECTED", "--review", ".proofloop/review.json");
    f.write(".proofloop/review.json", review);
    sameSnapshot(f.good("finish", "--review", ".proofloop/review.json"));
    f.good("status");
    f.good("run");
    assert.throws(() => readFileSync(statusPath), { code: "ENOENT" });
    assert.throws(() => readFileSync(finishPath), { code: "ENOENT" });
    rejects(f, "status", "REVIEW_INVALID");
    f.write("src/new.txt", "later");
    rejects(f, "finish", "STALE", "--review", ".proofloop/review.json");
  },
);
await scenario("baseline cannot be overwritten; unsafe run ID rejected", {}, (f) => {
  f.good("start");
  rejects(f, "start", "RUN_EXISTS");
  const r = f.call("status", "--id", "../escape");
  assert.notEqual(r.code, 0);
});
await scenario("staged-only out-of-scope content cannot evade the delta", {}, (f) => {
  f.write("outside.txt", "original");
  f.git("add", ".");
  f.git("commit", "-qm", "outside input");
  start(f);
  f.write("outside.txt", "staged change");
  f.git("add", "outside.txt");
  f.write("outside.txt", "original");
  rejects(f, "run", "OUT_OF_SCOPE");
});
await scenario("check cannot mutate its own input", {}, (f) => {
  f.write(
    "tests/journey.test.mjs",
    fixtureCode.replace(
      "JSON.stringify({ observed: 2 }));",
      "JSON.stringify({ observed: 2 })); writeFileSync('src/value.txt', '3');",
    ),
  );
  start(f);
  rejects(f, "run", "INPUT_CHANGED_DURING_CHECK");
});
await scenario(
  "missing executable cannot reuse success",
  {
    checks: [
      {
        id: "journey",
        criteria: ["outcome"],
        command: ["proofloop-intentionally-missing-executable"],
        cwd: ".",
        timeoutSeconds: 1,
        reporter: "node-tap",
        artifacts: [],
      },
    ],
  },
  (f) => {
    start(f);
    rejects(f, "run", "SPAWN_FAILED");
    rejects(f, "finish", "CHECK_FAILED");
  },
);
await scenario("repository lock rejects a second runner", {}, (f) => {
  start(f);
  f.write(".proofloop/runner.lock", "fixture lock");
  rejects(f, "run", "RUN_BUSY");
});
await scenario("policy traversal and source symlinks are rejected", {}, (f) => {
  rejects(f, "start", "Unsafe path", "--policy", "../escape.json");
  symlinkSync(f.root, join(f.root, "src/link"));
  rejects(f, "start", "Symlink unsupported");
});
await scenario("ignored direct driver and declared helper stay bound to evidence", {}, (f) => {
  f.write(".proofloop/check.test.mjs", fixtureCode);
  f.write(".proofloop/helper.txt", "seed");
  f.policy.checks[0].command = [
    process.execPath,
    "--test",
    "--test-reporter=tap",
    "check.test.mjs",
  ];
  f.policy.checks[0].cwd = ".proofloop";
  f.policy.checks[0].inputs = [".proofloop/helper.txt"];
  f.write(
    ".proofloop/check.test.mjs",
    fixtureCode.replace("'src/value.txt'", "'../src/value.txt'"),
  );
  f.write("proofloop.json", f.policy);
  start(f);
  f.good("run");
  const passed = f.good("finish");
  f.write(".proofloop/unrelated.log", "diagnostic");
  assert.equal(f.good("status").evidence, passed.evidence);
  f.write(".proofloop/helper.txt", "changed seed");
  const stale = rejects(f, "status", "INPUT_CHANGED");
  assert.notEqual(stale.evidence, passed.evidence);
  f.write(".proofloop/helper.txt", "seed");
  f.good("finish");
  f.write(".proofloop/check.test.mjs", "process.exit(1)");
  rejects(f, "finish", "INPUT_CHANGED");
  rmSync(join(f.root, ".proofloop/check.test.mjs"));
  rejects(f, "finish", "INPUT_CHANGED");
});
await scenario("ignored driver cannot rewrite itself during execution", {}, (f) => {
  f.write(
    ".proofloop/check.test.mjs",
    fixtureCode.replace(
      "JSON.stringify({ observed: 2 }));",
      "JSON.stringify({ observed: 2 })); writeFileSync('.proofloop/check.test.mjs', 'process.exit(1)');",
    ),
  );
  f.policy.checks[0].command[3] = ".proofloop/check.test.mjs";
  f.write("proofloop.json", f.policy);
  start(f);
  rejects(f, "run", "INPUT_CHANGED_DURING_CHECK");
});
await scenario("declared inputs reject unsafe paths and missing files", {}, (f) => {
  f.write(".proofloop/helper.txt", "safe");
  symlinkSync(join(f.root, ".proofloop/helper.txt"), join(f.root, ".proofloop/link"));
  for (const path of [
    "../escape",
    ".env",
    ".git/config",
    "./.git/config",
    ".proofloop/runs/data",
    ".proofloop/link",
    ".proofloop/missing",
  ]) {
    f.policy.checks[0].inputs = [path];
    f.write("proofloop.json", f.policy);
    assert.notEqual(f.call("start").code, 0, path);
  }
});
await scenario("empty artifact is distinguished from missing artifact", {}, (f) => {
  f.write("tests/journey.test.mjs", fixtureCode.replace("JSON.stringify({ observed: 2 })", "''"));
  start(f);
  rejects(f, "run", "ARTIFACT_EMPTY");
});
await scenario("process checks capture silent success and refuse failed retries", {}, (f) => {
  f.write(".proofloop/lint.mjs", "process.exit(0)");
  f.policy.checks.push({
    id: "lint",
    criteria: ["outcome"],
    command: [process.execPath, ".proofloop/lint.mjs"],
    cwd: ".",
    timeoutSeconds: 1,
    reporter: "exit-code",
    artifacts: [],
  });
  f.write("proofloop.json", f.policy);
  start(f);
  const run = f.good("run");
  assert.equal(run.checks[1].tests, 0);
  f.good("finish");
  f.write(".proofloop/lint.mjs", "process.exit(23)");
  const failed = rejects(f, "run", "CHECK_FAILED");
  assert.equal(failed.checks[1].exitCode, 23);
  assert.ok(!failed.checks[1].problems.some((p) => p.startsWith("REPORT_INVALID")));
  rejects(f, "finish", "CHECK_FAILED");
  f.write(".proofloop/lint.mjs", "setInterval(() => {}, 1000)");
  rejects(f, "run", "TIMEOUT");
});
await scenario("process success alone does not establish behavioral coverage", {}, (f) => {
  f.policy.checks[0].reporter = "exit-code";
  f.write("proofloop.json", f.policy);
  rejects(f, "start", "behavioral check");
});
await scenario("compact output links complete records without losing failures", {}, (f) => {
  start(f);
  const run = f.good("run", "--compact");
  assert.equal(run.checks[0].command, undefined);
  assert.equal(JSON.parse(readFileSync(run.record, "utf8")).checks[0].command.length, 4);
  const finish = f.good("finish", "--compact");
  assert.equal(finish.status, "verified");
  assert.equal(JSON.parse(readFileSync(finish.record, "utf8")).evidence, finish.evidence);
  f.write("src/value.txt", "3");
  rejects(f, "status", "STALE", "--compact");
});
writeFileSync(
  join(output, "result.json"),
  JSON.stringify(
    {
      command: "npm run acceptance",
      node: process.version,
      finishedAt: new Date().toISOString(),
      results,
    },
    null,
    2,
  ) + "\n",
);
for (const result of results) {
  console.log(
    `${result.passed ? "PASS" : "FAIL"} ${result.name}${result.error ? ": " + result.error : ""}`,
  );
}
console.log(`Artifact: ${join(output, "result.json")}`);
process.exitCode = results.every((r) => r.passed) ? 0 : 1;
