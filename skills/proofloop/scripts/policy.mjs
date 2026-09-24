export function requireThat(value, message) {
  if (!value) {
    throw new Error(message);
  }
}
function object(value) {
  requireThat(
    value !== null && typeof value === "object" && !Array.isArray(value),
    "Expected an object",
  );
}
function text(value) {
  requireThat(typeof value === "string" && value.trim().length > 0, "Expected a nonempty string");
}
function texts(value, nonempty = true) {
  requireThat(Array.isArray(value) && (!nonempty || value.length > 0), "Expected a string array");
  value.forEach(text);
}
export function safePath(value, pattern = false) {
  requireThat(
    value.length > 0 &&
      !value.startsWith("/") &&
      !value.includes("\\") &&
      !value.includes("\0") &&
      !value.includes(":") &&
      !value.split("/").some((part) => part === ".." || part === ""),
    `Unsafe path: ${value}`,
  );
  if (pattern) {
    requireThat(!/[[\]{}!]/.test(value), `Use only *, ** and ? globs: ${value}`);
  } else {
    requireThat(!/[?*]/.test(value), `Expected a literal path: ${value}`);
  }
}
export function matches(path, pattern) {
  let source = "^";
  for (let i = 0; i < pattern.length; i++) {
    const ch = pattern[i];
    if (ch === "*" && pattern[i + 1] === "*") {
      i++;
      if (pattern[i + 1] === "/") {
        source += "(?:.*/)?";
        i++;
      } else {
        source += ".*";
      }
    } else if (ch === "*") {
      source += "[^/]*";
    } else if (ch === "?") {
      source += "[^/]";
    } else {
      source += ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }
  }
  return new RegExp(source + "$").test(path);
}
export function validatePolicy(value) {
  object(value);
  text(value.goal);
  texts(value.allowedPaths);
  texts(value.testPatterns);
  for (const path of [...value.allowedPaths, ...value.testPatterns]) {
    safePath(path, true);
  }
  object(value.environment);
  text(value.environment.target);
  text(value.environment.seed);
  requireThat(Array.isArray(value.criteria) && value.criteria.length > 0, "Criteria required");
  const criteria = new Set();
  for (const c of value.criteria) {
    object(c);
    text(c.id);
    text(c.behavior);
    texts(c.failures);
    requireThat(!criteria.has(c.id), "Duplicate criterion");
    criteria.add(c.id);
  }
  requireThat(Array.isArray(value.checks) && value.checks.length > 0, "Checks required");
  const checks = new Set();
  const covered = new Set();
  for (const c of value.checks) {
    object(c);
    text(c.id);
    requireThat(/^[a-zA-Z0-9_-]+$/.test(c.id) && !checks.has(c.id), "Invalid/duplicate check ID");
    checks.add(c.id);
    texts(c.criteria);
    texts(c.command, true);
    text(c.cwd);
    safePath(c.cwd);
    requireThat(
      Number.isInteger(c.timeoutSeconds) &&
        Number(c.timeoutSeconds) > 0 &&
        Number(c.timeoutSeconds) <= 3600,
      "Timeout must be 1..3600 seconds",
    );
    requireThat(
      c.reporter === "node-tap" || c.reporter === "playwright-json",
      "Unsupported reporter",
    );
    texts(c.artifacts, false);
    c.artifacts.forEach((p) => safePath(p));
    for (const id of c.criteria) {
      requireThat(criteria.has(id), `Unknown criterion: ${id}`);
      covered.add(id);
    }
  }
  requireThat(
    [...criteria].every((id) => covered.has(id)),
    "Every criterion needs an executed check",
  );
  requireThat(Array.isArray(value.testChanges), "testChanges array required");
  const paths = new Set();
  for (const change of value.testChanges) {
    object(change);
    text(change.path);
    safePath(change.path);
    text(change.reason);
    texts(change.checks);
    requireThat(
      ["add", "modify", "delete"].includes(String(change.action)) && !paths.has(change.path),
      "Invalid/duplicate test change",
    );
    paths.add(change.path);
    requireThat(
      change.checks.every((id) => checks.has(id)),
      "Unknown replacement check",
    );
  }
  if (value.review !== null) {
    object(value.review);
    text(value.review.threadId);
    text(value.review.model);
    text(value.review.reasoning);
  }
  return value;
}
