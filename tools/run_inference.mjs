#!/usr/bin/env node
/** Offline inference CLI. */
import { resolve, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { EXACT_TWO_STEP, infer } from "../inference/kernel.mjs";
import { readJson, readUtf8 } from "./read_json.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const legacy = [
  "passive_twins", "interventional_split", "synchronized_mimicker",
  "model_class_refuted", "source_only",
];
const snapshots = [
  ...legacy.map(name => ({ name, policy: "pairwise" })),
  { name: "adaptive_categorical", policy: EXACT_TWO_STEP },
];
const CASE_BYTES = 64 * 1024;
const ATLAS_BYTES = 1024 * 1024;

function run(path, atlas, policy) {
  return JSON.stringify(infer(readJson(path, CASE_BYTES), atlas, policy), null, 2) + "\n";
}

function check(atlas) {
  let failures = 0;
  for (const { name, policy } of snapshots) {
    const actual = run(join(root, "inference/cases", name + ".json"), atlas, policy);
    const expected = readUtf8(join(root, "inference/results", name + ".json"), CASE_BYTES);
    if (actual !== expected) {
      console.error("SNAPSHOT_MISMATCH " + name);
      failures++;
    }
  }
  if (failures > 0) return 1;
  console.log(`INFERENCE_CONFORMANCE: ${snapshots.length}/${snapshots.length} snapshots match`);
  return 0;
}

function main(argv) {
  const checking = argv.length === 1 && argv[0] === "--check";
  const exact = argv.length === 2 && argv[0] === "--exact-two-step" && !argv[1].startsWith("-");
  const ordinary = argv.length === 1 && !argv[0].startsWith("-");
  if (!checking && !exact && !ordinary) {
    console.error("Usage: node tools/run_inference.mjs --check | [--exact-two-step] <local-case.json>");
    return 2;
  }
  const atlas = readJson(join(root, "research/atlas.json"), ATLAS_BYTES);
  if (checking) return check(atlas);
  process.stdout.write(run(resolve(exact ? argv[1] : argv[0]), atlas, exact ? EXACT_TWO_STEP : "pairwise"));
  return 0;
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
