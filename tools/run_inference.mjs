#!/usr/bin/env node
/** Offline inference CLI. */
import { resolve, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { EXACT_CLASS_TWO_STEP, EXACT_TWO_STEP, infer } from "../inference/kernel.mjs";
import { advanceReceipt, createReceipt, verifyReceipt } from "../inference/receipt.mjs";
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

const input = path => readJson(resolve(path), CASE_BYTES);

function print(result) {
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  return 0;
}

function main(argv) {
  const [flag, ...paths] = argv;
  const arities = new Map([
    ["--check", 0], ["--exact-two-step", 1], ["--exact-class-two-step", 1],
    ["--receipt", 1], ["--receipt-class", 1], ["--verify-receipt", 2], ["--verify-anchored-receipt", 3], ["--advance-receipt", 3],
  ]);
  const ordinary = argv.length === 1 && !flag.startsWith("-");
  if (!ordinary && (arities.get(flag) !== paths.length || paths.some(path => path.startsWith("-")))) {
    console.error("Usage: node tools/run_inference.mjs --check | [--exact-two-step|--exact-class-two-step|--receipt|--receipt-class] <case.json> | --verify-receipt <case.json> <receipt.json> | --verify-anchored-receipt <case.json> <receipt.json> <trusted-sha256> | --advance-receipt <prior-case.json> <receipt.json> <new-case.json>");
    return 2;
  }

  const atlas = readJson(join(root, "research/atlas.json"), ATLAS_BYTES);
  if (ordinary) return print(infer(input(flag), atlas));
  if (flag === "--check") return check(atlas);
  if (flag === "--verify-receipt" || flag === "--verify-anchored-receipt") {
    verifyReceipt(input(paths[0]), atlas, input(paths[1]), paths[2]);
    return print({ status: "RECEIPT_VERIFIED" });
  }
  if (flag === "--advance-receipt") {
    return print(advanceReceipt(input(paths[0]), input(paths[2]), atlas, input(paths[1])));
  }
  const policy = flag === "--exact-class-two-step" || flag === "--receipt-class"
    ? EXACT_CLASS_TWO_STEP : EXACT_TWO_STEP;
  const caseData = input(paths[0]);
  if (flag === "--receipt" || flag === "--receipt-class") return print(createReceipt(caseData, atlas, policy));
  return print(infer(caseData, atlas, policy));
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
