import { readFileSync, writeFileSync } from "node:fs";

const { version } = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
writeFileSync(
  new URL("../skills/proofloop/version.json", import.meta.url),
  JSON.stringify({ version }, null, 2) + "\n",
);
