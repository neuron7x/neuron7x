import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {resolve,join,dirname} from "node:path";
import {fileURLToPath} from "node:url";
import {PROTOCOL,DEBT,validate,infer} from "../inference/kernel.mjs";
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
