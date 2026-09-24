import { createHash, randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  existsSync,
  lstatSync,
  readFileSync,
  realpathSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { matches, requireThat, safePath } from "./policy.mjs";
export const sha = (data) => createHash("sha256").update(data).digest("hex");
export const digest = (data) => sha(JSON.stringify(data));
export function git(root, ...args) {
  return execFileSync("git", ["-C", root, ...args], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
}
export function inside(root, path) {
  safePath(path);
  const full = resolve(root, path);
  requireThat(full === root || full.startsWith(root + sep), `Path escapes root: ${path}`);
  let cursor = root;
  for (const part of relative(root, full).split(sep).filter(Boolean)) {
    cursor = join(cursor, part);
    requireThat(
      !lstatSync(cursor, { throwIfNoEntry: false })?.isSymbolicLink(),
      `Symlink unsupported: ${path}`,
    );
  }
  return full;
}
export const readJSON = (path) => JSON.parse(readFileSync(path, "utf8"));
export function writeJSON(path, value) {
  const temp = `${path}.${randomUUID()}.tmp`;
  writeFileSync(temp, JSON.stringify(value, null, 2) + "\n", { mode: 0o600, flag: "wx" });
  renameSync(temp, path);
}
const sensitive = [
  "**/.env",
  "**/.env.*",
  "**/*.pem",
  "**/*.key",
  "**/credentials*",
  "**/secrets/**",
];
export const isSensitive = (path) => sensitive.some((p) => matches(path, p));
export function snapshot(root) {
  const paths = new Set(
    git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
      .split("\0")
      .filter(Boolean),
  );
  const files = {};
  for (const path of [...paths].sort()) {
    if (path === ".proofloop" || path.startsWith(".proofloop/")) {
      continue;
    }
    const full = inside(root, path);
    if (!existsSync(full)) {
      continue;
    }
    const stat = lstatSync(full);
    requireThat(stat.isFile(), `Only regular repository files supported: ${path}`);
    files[path] = isSensitive(path)
      ? `excluded:${stat.size}:${stat.mtimeMs}:${stat.mode}`
      : sha(Buffer.concat([Buffer.from(`${stat.mode}:`), readFileSync(full)]));
  }
  const index = git(root, "ls-files", "--stage", "-z");
  const indexFiles = {};
  for (const entry of index.split("\0").filter(Boolean)) {
    const split = entry.indexOf("\t");
    const path = entry.slice(split + 1);
    indexFiles[path] = (indexFiles[path] ?? "") + entry.slice(0, split) + "\n";
  }
  const state = {
    root: realpathSync(root),
    head: git(root, "rev-parse", "HEAD").trim(),
    index: sha(index),
    indexFiles,
    files,
  };
  return { ...state, fingerprint: digest(state) };
}
export function changedPaths(before, after) {
  return [
    ...new Set([
      ...Object.keys(before.files),
      ...Object.keys(after.files),
      ...Object.keys(before.indexFiles),
      ...Object.keys(after.indexFiles),
    ]),
  ]
    .filter(
      (p) => before.files[p] !== after.files[p] || before.indexFiles[p] !== after.indexFiles[p],
    )
    .sort();
}
export function ensureArtifact(path, nonempty = true) {
  const stat = lstatSync(path);
  requireThat(
    stat.isFile() && (!nonempty || stat.size > 0),
    "Artifact must be a nonempty regular file",
  );
  return sha(readFileSync(path));
}
// Direct file arguments plus explicitly declared helpers; not an import-graph resolver.
export function checkInputs(root, check) {
  const paths = new Set(
    (check.inputs ?? []).map((path) => relative(root, inside(root, path)).split(sep).join("/")),
  );
  const cwd = inside(root, check.cwd);
  for (const arg of check.command) {
    if (arg.startsWith("-") || arg.includes("\n") || arg.includes("\0")) {
      continue;
    }
    const full = resolve(cwd, arg);
    if (full.startsWith(root + sep) && existsSync(full)) {
      const path = relative(root, full).split(sep).join("/");
      // Reject symlinks even when their target is a directory.
      if (lstatSync(inside(root, path)).isFile()) {
        paths.add(path);
      }
    }
  }
  const inputs = {};
  for (const path of [...paths].sort()) {
    requireThat(
      !isSensitive(path) &&
        path !== ".git" &&
        !path.startsWith(".git/") &&
        path !== ".proofloop/runner.lock" &&
        path !== ".proofloop/runs" &&
        !path.startsWith(".proofloop/runs/"),
      `Unsupported check input: ${path}`,
    );
    const full = inside(root, path);
    const stat = lstatSync(full);
    requireThat(stat.isFile(), `Check input must be a regular file: ${path}`);
    inputs[path] = sha(Buffer.concat([Buffer.from(`${stat.mode}:`), readFileSync(full)]));
  }
  return inputs;
}
