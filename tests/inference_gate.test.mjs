import test from "node:test";
import { spawnSync } from "node:child_process";
import assert from "node:assert/strict";
import {cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import {resolve,join,dirname} from "node:path";
import {fileURLToPath} from "node:url";
import {PROTOCOL,DEBT,EXACT_TWO_STEP,validate,infer} from "../inference/kernel.mjs";
const root=resolve(dirname(fileURLToPath(import.meta.url)),"..");
const atlas=JSON.parse(readFileSync(join(root,"research/atlas.json"),"utf8"));
const names=["passive_twins","interventional_split","synchronized_mimicker","model_class_refuted","source_only"];
const get=n=>JSON.parse(readFileSync(join(root,"inference/cases/"+n+".json"),"utf8"));
const cp=x=>JSON.parse(JSON.stringify(x));
test("snapshots byte exact",()=>{
 for(const n of names)assert.equal(JSON.stringify(infer(get(n),atlas),null,2)+"\n",readFileSync(join(root,"inference/results/"+n+".json"),"utf8"));
});
test("passive twins abstain and propose experiment",()=>{
 const r=infer(get("passive_twins"),atlas);
 assert.equal(r.verdict,"ABSTAIN");assert.equal(r.next_intervention,"do_toggle");assert.equal(r.survivors.length,2);
});
test("intervention selects model conditionally but never grants causality",()=>{
 const r=infer(get("interventional_split"),atlas);
 assert.equal(r.verdict,"CONDITIONAL_MODEL_SELECTION");assert.deepEqual(r.survivors,["AGENCY"]);
 assert.equal(r.causal_authority,false);assert.equal(r.independent_replication,false);assert.deepEqual(r.unresolved_assumptions,DEBT);
});
test("synchronized mimicker abstains",()=>{
 const r=infer(get("synchronized_mimicker"),atlas);assert.equal(r.verdict,"ABSTAIN");assert.equal(r.survivors.length,2);
});
test("counterexample rejects candidate model class only",()=>{
 const r=infer(get("model_class_refuted"),atlas);assert.equal(r.verdict,"MODEL_CLASS_REFUTED");assert.deepEqual(r.survivors,[]);
});
test("atlas source pointer is not experiment",()=>{
 const r=infer(get("source_only"),atlas);assert.equal(r.verdict,"ABSTAIN");assert.equal(r.used_experiments.length,0);
});
test("source mismatch abstains without causal authority",()=>{
 const c=get("passive_twins");c.source.commit="a".repeat(40);
 assert.equal(infer(c,atlas).reason,"SOURCE_MISMATCH");assert.equal(infer(c,atlas).causal_authority,false);
});
test("permutation invariance",()=>{
 const a=get("interventional_split"),b=cp(a);b.models.reverse();b.experiments.reverse();b.observations.reverse();
 assert.deepEqual(infer(a,atlas),infer(b,atlas));
});
test("invalid input fails closed",()=>{
 const mutations=[
  c=>c.budget=0,
  c=>delete c.models[0].predictions.do_toggle,
  c=>c.observations.push({experiment:"observe",outcome:"ONE"}),
  c=>c.models[1].id=c.models[0].id,
  c=>c.observations[0].outcome="<script>",
  c=>c.source.commit="HEAD",
  c=>c.unexpected=true,
  c=>c.experiments[1].kind="invalid"
 ];
 for(const m of mutations){const c=get("passive_twins");m(c);assert.throws(()=>validate(c));}
});
test("repeatability without randomness or remote model",()=>{
 assert.equal(PROTOCOL,"neuron7x.conditional-inference.v1");
 for(let i=0;i<20;i++)assert.deepEqual(infer(get("interventional_split"),atlas),infer(get("interventional_split"),atlas));
});

function exactCase(rows, budget = 3) {
  const c = get("passive_twins");
  const interventions = Array.from({ length: rows[0].length }, (_, index) => "ABCD"[index]);
  c.budget = budget;
  c.experiments = [
    { id: "observe", kind: "observation" },
    ...interventions.map(id => ({ id, kind: "intervention" })),
  ];
  c.models = rows.map((row, index) => ({
    id: `M${index}`,
    predictions: {
      observe: "ZERO",
      ...Object.fromEntries(interventions.map((id, column) => [id, row[column]])),
    },
  }));
  return c;
}

test("exact policy plans different continuations for categorical outcomes", () => {
  const c = get("adaptive_categorical");
  assert.equal(infer(c, atlas).next_intervention, "C");
  const initial = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(initial.verdict, "ABSTAIN");
  assert.equal(initial.next_intervention, "A");
  assert.deepEqual(initial.intervention_plan, { horizon: 2, selected_models: 5, intervention_uses: 10 });
  for (const target of c.models) {
    const branch = cp(c);
    branch.observations.push({ experiment: "A", outcome: target.predictions.A });
    const second = infer(branch, atlas, EXACT_TWO_STEP).next_intervention;
    assert.equal(second, target.predictions.A === "0" ? "B" : "C");
    branch.observations.push({ experiment: second, outcome: target.predictions[second] });
    const result = infer(branch, atlas, EXACT_TWO_STEP);
    assert.equal(result.verdict, "CONDITIONAL_MODEL_SELECTION");
    assert.deepEqual(result.survivors, [target.id]);
    assert.equal(result.next_intervention, null);
    assert.equal(result.causal_authority, false);
    assert.equal(result.independent_replication, false);
  }
  c.models.reverse();
  c.experiments.reverse();
  assert.deepEqual(infer(c, atlas, EXACT_TWO_STEP), initial);
});

test("one remaining record is valued by admissible selections and arbitrary category labels", () => {
  const binary = exactCase(["00", "00", "10", "11"], 2);
  assert.equal(infer(binary, atlas).next_intervention, "A");
  assert.equal(infer(binary, atlas, EXACT_TWO_STEP).next_intervention, "B");
  const categorical = exactCase([
    ["constructor", "0"], ["toString", "0"], ["__proto__", "0"], ["__proto__", "1"],
  ], 2);
  const plan = infer(categorical, atlas, EXACT_TWO_STEP);
  assert.equal(plan.next_intervention, "A");
  assert.deepEqual(plan.intervention_plan, { horizon: 1, selected_models: 2, intervention_uses: 4 });
});

test("witness admission and unnecessary interventions remain distinct", () => {
  const c = exactCase(["00", "01"]);
  c.models[1].predictions.observe = "ONE";
  const start = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(start.verdict, "ABSTAIN");
  assert.equal(start.next_intervention, "B");
  assert.deepEqual(start.intervention_plan, { horizon: 2, selected_models: 1, intervention_uses: 1 });
  c.observations.push({ experiment: "B", outcome: "0" });
  const observed = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(observed.verdict, "CONDITIONAL_MODEL_SELECTION");
  assert.equal(observed.next_intervention, null);
  assert.equal(observed.intervention_plan.intervention_uses, 0);
});

test("exact policy abstains within its horizon and fails closed at the existing boundaries", () => {
  const cube = exactCase(Array.from({ length: 8 }, (_, n) => n.toString(2).padStart(3, "0")), 4);
  const zero = infer(cube, atlas, EXACT_TWO_STEP);
  assert.equal(zero.reason, "NO_SELECTION_WITHIN_PLANNING_HORIZON");
  assert.equal(zero.next_intervention, null);
  assert.equal(zero.intervention_plan.selected_models, 0);
  assert.ok(infer(cube, atlas).next_intervention);

  const c = get("passive_twins");
  c.budget = 1;
  const exhausted = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(exhausted.intervention_plan.horizon, 0);
  assert.equal(exhausted.next_intervention, null);
  c.source.commit = "a".repeat(40);
  const mismatch = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(mismatch.reason, "SOURCE_MISMATCH");
  assert.equal(mismatch.next_intervention, null);
  assert.ok(!Object.hasOwn(mismatch, "intervention_plan"));
  const refuted = infer(get("model_class_refuted"), atlas, EXACT_TWO_STEP);
  assert.equal(refuted.verdict, "MODEL_CLASS_REFUTED");
  assert.equal(refuted.next_intervention, null);
  assert.throws(() => infer(c, atlas, "UNKNOWN"), /INVALID_INTERVENTION_POLICY/);
});

test("prediction columns are exact keys, even when an extra name joins missing columns", () => {
  const c = get("adaptive_categorical");
  for (const model of c.models) {
    model.predictions["A|B"] = model.predictions.A;
    delete model.predictions.A;
    delete model.predictions.B;
  }
  for (const policy of ["pairwise", EXACT_TWO_STEP]) {
    assert.throws(() => infer(c, atlas, policy), /INCOMPLETE_PREDICTIONS/);
  }
});

test("source binding requires both the declared project and its pinned commit", () => {
  const c = get("passive_twins");
  c.source.project = "different_project";
  for (const policy of ["pairwise", EXACT_TWO_STEP]) {
    const result = infer(c, atlas, policy);
    assert.equal(result.reason, "SOURCE_MISMATCH");
    assert.equal(result.next_intervention, null);
    assert.equal(result.causal_authority, false);
    assert.ok(!Object.hasOwn(result, "intervention_plan"));
  }
});

test("an observed constant intervention grants no witness", () => {
  const c = exactCase(["000", "000"], 4);
  c.models[1].predictions.observe = "ONE";
  c.observations.push({ experiment: "A", outcome: "0" });
  const result = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(result.verdict, "ABSTAIN");
  assert.equal(result.reason, "NO_DISCRIMINATING_INTERVENTION_OBSERVED");
  assert.equal(result.next_intervention, null);
  assert.deepEqual(result.intervention_plan, { horizon: 2, selected_models: 0, intervention_uses: 0 });
  assert.equal(infer(c, atlas).verdict, "ABSTAIN");
});

test("exact policy ranks by total cost before lexical tie resolution", () => {
  const c = exactCase(["000", "011", "122", "133"]);
  c.experiments.reverse();
  const result = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(result.next_intervention, "B");
  assert.deepEqual(result.intervention_plan, { horizon: 2, selected_models: 4, intervention_uses: 4 });
});

test("recorded interventions and unused admissible probes bound the horizon", () => {
  const c = exactCase(["000", "000", "010", "011", "100"], 3);
  c.observations.push({ experiment: "A", outcome: "0" });
  const one = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(one.next_intervention, "C");
  assert.deepEqual(one.intervention_plan, { horizon: 1, selected_models: 1, intervention_uses: 4 });
  c.budget = 4;
  const two = infer(c, atlas, EXACT_TWO_STEP);
  assert.equal(two.next_intervention, "B");
  assert.deepEqual(two.intervention_plan, { horizon: 2, selected_models: 2, intervention_uses: 6 });

  const available = exactCase(["0", "1"], 3);
  const clipped = infer(available, atlas, EXACT_TWO_STEP);
  assert.equal(clipped.next_intervention, "A");
  assert.equal(clipped.intervention_plan.horizon, 1);
  available.observations.push({ experiment: "A", outcome: "0" });
  const done = infer(available, atlas, EXACT_TWO_STEP);
  assert.equal(done.next_intervention, null);
  assert.equal(done.intervention_plan.horizon, 0);
});

test("CLI dispatches the exact policy and rejects malformed invocations", () => {
  const cli = join(root, "tools/run_inference.mjs");
  const fixture = join(root, "inference/cases/adaptive_categorical.json");
  const run = (...args) => spawnSync(process.execPath, [cli, ...args], { encoding: "utf8" });
  const exact = run("--exact-two-step", fixture);
  assert.equal(exact.status, 0, exact.stderr);
  const planned = JSON.parse(exact.stdout);
  assert.equal(planned.intervention_policy, EXACT_TWO_STEP);
  assert.equal(planned.next_intervention, "A");
  assert.equal(planned.verdict, "ABSTAIN");
  assert.equal(planned.intervention_plan.selected_models, 5);
  const legacy = run(fixture);
  assert.equal(legacy.status, 0, legacy.stderr);
  const greedy = JSON.parse(legacy.stdout);
  assert.equal(greedy.next_intervention, "C");
  assert.ok(!Object.hasOwn(greedy, "intervention_policy"));
  for (const args of [["--exact-two-step"], ["--unknown", fixture]]) {
    const invalid = run(...args);
    assert.equal(invalid.status, 2);
    assert.equal(invalid.stdout, "");
    assert.match(invalid.stderr, /Usage/);
  }
});

test("CLI conformance exits nonzero when a reference trace differs", t => {
  const copy = mkdtempSync(join(tmpdir(), "inference-conformance-"));
  t.after(() => rmSync(copy, { recursive: true, force: true }));
  for (const directory of ["inference", "research", "tools"]) {
    mkdirSync(join(copy, directory));
  }
  for (const file of [
    "inference/kernel.mjs",
    "inference/two_step_policy.mjs",
    "inference/cases",
    "inference/results",
    "research/atlas.json",
    "tools/run_inference.mjs",
  ]) {
    cpSync(join(root, file), join(copy, file), { recursive: true });
  }

  const run = () => spawnSync(process.execPath, [join(copy, "tools/run_inference.mjs"), "--check"], { encoding: "utf8" });
  const baseline = run();
  assert.equal(baseline.status, 0, baseline.stderr);
  assert.match(baseline.stdout, /5\/5 snapshots match/);

  writeFileSync(join(copy, "inference/results/passive_twins.json"), "{}\n");
  const changed = run();
  assert.equal(changed.status, 1);
  assert.match(changed.stderr, /SNAPSHOT_MISMATCH passive_twins/);
  assert.equal(changed.stdout, "");
});
