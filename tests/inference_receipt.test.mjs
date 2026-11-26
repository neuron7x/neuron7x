import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { EXACT_CLASS_TWO_STEP, EXACT_TWO_STEP, infer } from "../inference/kernel.mjs";
import { advanceReceipt, createReceipt, verifyReceipt } from "../inference/receipt.mjs";

const read = name => JSON.parse(readFileSync(new URL("../" + name, import.meta.url), "utf8"));
const atlas = read("research/atlas.json");
const fixture = name => read("inference/cases/" + name + ".json");
const add = (input, experiment, outcome) => ({
  ...input, observations: [...input.observations, { experiment, outcome }],
});

test("a changed rival invalidates the receipt even if the exact verdict is unchanged", () => {
  const input = fixture("interventional_split");
  const receipt = createReceipt(input, atlas);
  assert.deepEqual(verifyReceipt(input, atlas, receipt), receipt);

  const extra = structuredClone(input);
  extra.experiments.push({ id: "unused", kind: "intervention" });
  for (const model of extra.models) model.predictions.unused = "ZERO";
  const oldExtra = createReceipt(extra, atlas);
  extra.models.find(model => model.id === "MIMIC").predictions.unused = "ONE";
  const newExtra = createReceipt(extra, atlas);
  assert.deepEqual(newExtra.result, oldExtra.result);
  assert.deepEqual(newExtra.evidence, oldExtra.evidence);
  assert.throws(() => verifyReceipt(extra, atlas, oldExtra), /RECEIPT_MISMATCH/);

  const changed = structuredClone(input);
  changed.models.find(model => model.id === "MIMIC").predictions.observe = "ONE";
  assert.deepEqual(infer(changed, atlas, EXACT_TWO_STEP), receipt.result);
  assert.throws(() => verifyReceipt(changed, atlas, receipt), /RECEIPT_MISMATCH/);
  assert.throws(() => verifyReceipt(input, { ...atlas, verified_date: "2025-01-01" }, receipt), /RECEIPT_MISMATCH/);
  const reorderedObject = Object.fromEntries(Object.entries(input).reverse());
  assert.deepEqual(createReceipt(reorderedObject, atlas), receipt);

  assert.equal(receipt.evidence.witness_record, 1);
  assert.deepEqual(receipt.evidence.exclusions, [{ model: "MIMIC", record: 1, predicted: "ZERO" }]);
  const forged = structuredClone(receipt);
  forged.evidence.witness_record = 0;
  assert.throws(() => verifyReceipt(input, atlas, forged), /RECEIPT_MISMATCH/);
  const sparse = structuredClone(receipt);
  sparse.forecast.branches = Array(1);
  assert.throws(() => verifyReceipt(input, atlas, sparse), /INVALID_RECEIPT_VALUE/);
  const changedOutput = structuredClone(receipt);
  changedOutput.result.causal_authority = true;
  assert.throws(() => verifyReceipt(input, atlas, changedOutput), /RECEIPT_MISMATCH/);
  const editedTrace = { ...input, observations: input.observations.slice(0, 1) };
  assert.throws(() => verifyReceipt(editedTrace, atlas, receipt), /INVALID_RECEIPT_PREFIX/);
});

test("a two-step commitment fixes per-outcome continuations and allows out-of-class evidence", () => {
  const input = { ...fixture("adaptive_categorical"), budget: 4 };
  const root = createReceipt(input, atlas);
  assert.deepEqual(root.forecast, { first: "A", branches: [
    { outcome: "0", next: "B" }, { outcome: "1", next: "C" },
  ] });
  assert.equal(root.result.verdict, "ABSTAIN");
  assert.equal(root.evidence.witness_record, null);
  for (const target of input.models) {
    const step = add(input, "A", target.predictions.A);
    const receipt = advanceReceipt(input, step, atlas, root);
    assert.deepEqual(verifyReceipt(step, atlas, receipt), receipt);
    const second = target.predictions.A === "0" ? "B" : "C";
    assert.equal(receipt.result.next_intervention, second);
    const final = add(step, second, target.predictions[second]);
    const terminal = advanceReceipt(step, final, atlas, receipt);
    assert.deepEqual(terminal.result.survivors, [target.id]);
    assert.equal(terminal.result.next_intervention, null);
    assert.equal(terminal.result.intervention_plan.horizon, 0);
    assert.equal(terminal.result.causal_authority, false);
    assert.ok(terminal.evidence.witness_record >= 1);
  }
  assert.throws(() => advanceReceipt(input, add(input, "B", "0"), atlas, root), /RECEIPT_PLAN_MISMATCH/);
  const wrongPrior = add({ ...input, observations: [{ experiment: "observe", outcome: "ONE" }] }, "A", "0");
  assert.throws(() => advanceReceipt(input, wrongPrior, atlas, root), /RECEIPT_HISTORY_MISMATCH/);
  const surprise = advanceReceipt(input, add(input, "A", "UNMODELED"), atlas, root);
  assert.equal(surprise.result.verdict, "MODEL_CLASS_REFUTED");
  assert.equal(surprise.evidence.exclusions.length, input.models.length);
  assert.equal(surprise.evidence.witness_record, null);
});

test("an order-dependent behavior needs a different declaration protocol", () => {
  function simulate(trace, readsState) {
    let set = false;
    return trace.map(action => {
      if (action === "A") {
        set = true;
        return "ACK";
      }
      return readsState && set ? "ONE" : "ZERO";
    });
  }
  assert.notDeepEqual(simulate(["A", "B"], true), simulate(["A", "B"], false));
  assert.deepEqual(simulate(["B", "A"], true), simulate(["B", "A"], false));
  const temporal = { ...fixture("adaptive_categorical"), history: { response: "ORDER_DEPENDENT" } };
  for (const policy of [EXACT_TWO_STEP, EXACT_CLASS_TWO_STEP]) {
    assert.throws(() => createReceipt(temporal, atlas, policy), /INVALID_CASE/);
  }
});

test("duplicating a behavior changes ID-based selection but keeps the class policy", () => {
  const input = fixture("passive_twins");
  input.experiments = [
    { id: "observe", kind: "observation" },
    { id: "A", kind: "intervention" },
    { id: "B", kind: "intervention" },
  ];
  input.models = ["00", "10", "11"].map(([A, B], index) => ({
    id: "M" + index, predictions: { observe: "ZERO", A, B },
  }));
  const alias = { ...input, models: [...input.models, { ...input.models[0], id: "Alias" }] };
  assert.equal(infer(input, atlas, EXACT_TWO_STEP).next_intervention, "A");
  assert.equal(infer(alias, atlas, EXACT_TWO_STEP).next_intervention, "B");
  const baseline = infer(input, atlas, EXACT_CLASS_TWO_STEP);
  const grouped = infer(alias, atlas, EXACT_CLASS_TWO_STEP);
  assert.deepEqual(grouped.behavior_classes, { declared: 3, surviving: 3 });
  assert.deepEqual(grouped.intervention_plan, baseline.intervention_plan);
  assert.equal(grouped.next_intervention, baseline.next_intervention);
  const root = createReceipt(alias, atlas, EXACT_CLASS_TWO_STEP);
  const result = advanceReceipt(alias, add(alias, "A", "0"), atlas, root);
  assert.equal(result.result.verdict, "CONDITIONAL_BEHAVIOR_CLASS_SELECTION");
  assert.deepEqual(result.result.survivors, ["Alias", "M0"]);
  assert.equal(result.result.causal_authority, false);
});

test("receipt commands bind and verify real case files", t => {
  const dir = mkdtempSync(join(tmpdir(), "inference-receipts-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const cli = fileURLToPath(new URL("../tools/run_inference.mjs", import.meta.url));
  const prior = join(dir, "prior.json");
  const current = join(dir, "current.json");
  const path = join(dir, "receipt.json");
  const input = fixture("adaptive_categorical");
  writeFileSync(prior, JSON.stringify(input));
  writeFileSync(current, JSON.stringify(add(input, "A", "1")));
  const run = (...args) => spawnSync(process.execPath, [cli, ...args], { encoding: "utf8" });

  const created = run("--receipt", prior);
  assert.equal(created.status, 0, created.stderr);
  writeFileSync(path, created.stdout);
  assert.equal(run("--verify-receipt", prior, path).status, 0);
  const advanced = run("--advance-receipt", prior, path, current);
  assert.equal(advanced.status, 0, advanced.stderr);
  assert.equal(JSON.parse(advanced.stdout).result.next_intervention, "C");
  const stale = run("--verify-receipt", current, path);
  assert.equal(stale.status, 1);
  assert.equal(stale.stdout, "");
  assert.match(stale.stderr, /RECEIPT_MISMATCH/);
  const classes = run("--receipt-class", prior);
  assert.equal(classes.status, 0, classes.stderr);
  assert.equal(JSON.parse(classes.stdout).policy, EXACT_CLASS_TWO_STEP);
});

test("receipt continuation keeps the forecast when rolling inference would change it", () => {
  const input = fixture("passive_twins");
  const interventions = ["A", "B", "C", "D"];
  input.budget = 4;
  input.experiments = [input.experiments[0], ...interventions.map(id => ({ id, kind: "intervention" }))];
  input.models = ["0101", "0011", "0001", "1010", "1001", "1110"].map((row, index) => ({
    id: "M" + index,
    predictions: { observe: "ZERO", ...Object.fromEntries(interventions.map((id, i) => [id, row[i]])) },
  }));
  const receipt = createReceipt(input, atlas);
  assert.equal(receipt.forecast.first, "B");
  const first = add(input, "B", "0");
  assert.equal(infer(first, atlas, EXACT_TWO_STEP).next_intervention, "A");
  const verified = advanceReceipt(input, first, atlas, receipt);
  assert.equal(verified.result.next_intervention, "D");
  assert.throws(() => advanceReceipt(first, add(first, "A", "0"), atlas, verified), /RECEIPT_PLAN_MISMATCH/);
  assert.doesNotThrow(() => verifyReceipt(first, atlas, verified));
});
