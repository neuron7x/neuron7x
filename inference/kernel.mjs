/** NEURON7X Conditional Inference Gate v1 — finite-model discrimination, not causal proof. */
export const PROTOCOL = "neuron7x.conditional-inference.v1";
export const DEBT = Object.freeze(["candidate_class_completeness","intervention_fidelity","outcome_provenance","unmodelled_exogenous_mimickers"]);
const ID = /^[A-Za-z][A-Za-z0-9:_-]{0,47}$/;
const SHA = /^[0-9a-f]{40}$/;
const obj = x => x !== null && typeof x === "object" && !Array.isArray(x);
const exact = (x,ks) => obj(x) && Object.keys(x).sort().join("|")===ks.slice().sort().join("|");
const name = x => typeof x==="string" && ID.test(x);
const category = x => typeof x==="string" && /^[A-Za-z0-9_.:-]{1,32}$/.test(x);
export function validate(x) {
  if(!exact(x,["schema","case_id","basis","source","budget","experiments","models","observations"])||x.schema!==PROTOCOL||!name(x.case_id)) throw Error("INVALID_CASE");
  if(!["synthetic","unverified_external"].includes(x.basis))throw Error("INVALID_BASIS");
  if(!exact(x.source,["project","commit"])||!name(x.source.project)||!SHA.test(x.source.commit))throw Error("INVALID_SOURCE");
  if(!Number.isSafeInteger(x.budget)||x.budget<1||x.budget>32)throw Error("INVALID_BUDGET");
  if(!Array.isArray(x.experiments)||x.experiments.length<2||x.experiments.length>8)throw Error("INVALID_EXPERIMENTS");
  const ids=new Set(); let passive=0,active=0;
  for(const e of x.experiments){
    if(!exact(e,["id","kind"])||!name(e.id)||ids.has(e.id))throw Error("INVALID_EXPERIMENT");
    ids.add(e.id);
    if(e.kind==="observation")passive++;
    else if(e.kind==="intervention")active++;
    else throw Error("INVALID_EXPERIMENT_KIND");
  }
  if(passive!==1||active<1)throw Error("INVALID_EXPERIMENT_DESIGN");
  if(!Array.isArray(x.models)||x.models.length<2||x.models.length>8)throw Error("INVALID_MODEL_SET");
  const models=new Set();
  for(const m of x.models){
    if(!exact(m,["id","predictions"])||!name(m.id)||models.has(m.id))throw Error("INVALID_MODEL");
    models.add(m.id);
    if(!obj(m.predictions)||Object.keys(m.predictions).sort().join("|")!==[...ids].sort().join("|"))throw Error("INCOMPLETE_PREDICTIONS");
    if(!Object.values(m.predictions).every(category))throw Error("INVALID_PREDICTION");
  }
  if(!Array.isArray(x.observations)||x.observations.length>x.budget)throw Error("BUDGET_EXCEEDED");
  const seen=new Set();
  for(const o of x.observations){
    if(!exact(o,["experiment","outcome"])||!ids.has(o.experiment)||!category(o.outcome)||seen.has(o.experiment))throw Error("INVALID_OBSERVATION");
    seen.add(o.experiment);
  }
  return x;
}
export function infer(x,atlas) {
  validate(x);
  if(!obj(atlas)||atlas.schema!=="neuron7x.research-atlas.v1"||!Array.isArray(atlas.projects))throw Error("INVALID_ATLAS");
  const pinned=atlas.projects.some(p=>p.slug===x.source.project&&p.commit===x.source.commit);
  const base={protocol:PROTOCOL,case_id:x.case_id,basis:x.basis,
    source_status:pinned?"PINNED_REFERENCE_ONLY":"SOURCE_MISMATCH",
    causal_authority:false,independent_replication:false,unresolved_assumptions:DEBT.slice()};
  if(!pinned)return {...base,verdict:"ABSTAIN",reason:"SOURCE_MISMATCH",survivors:[],excluded:[],used_experiments:[],next_intervention:null};
  const ms=x.models.slice().sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);
  const obs=x.observations.slice().sort((a,b)=>a.experiment<b.experiment?-1:a.experiment>b.experiment?1:0);
  const keep=ms.filter(m=>obs.every(o=>m.predictions[o.experiment]===o.outcome));
  const excluded=ms.filter(m=>!keep.includes(m)).map(m=>m.id);
  const used=obs.map(o=>o.experiment);
  let next=null,score=0;
  const tests=x.experiments.filter(e=>e.kind==="intervention").slice().sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);
  for(const e of tests){
    if(used.includes(e.id))continue;
    let pairs=0;
    for(let i=0;i<keep.length;i++)for(let j=i+1;j<keep.length;j++)
      if(keep[i].predictions[e.id]!==keep[j].predictions[e.id])pairs++;
    if(pairs>score){next=e.id;score=pairs;}
  }
  if(used.length>=x.budget)next=null;
  let verdict="ABSTAIN",reason="INSUFFICIENT_DISCRIMINATION";
  if(keep.length===0){verdict="MODEL_CLASS_REFUTED";reason="NO_DECLARED_MODEL_EXPLAINS_RECORD";}
  else if(keep.length===1){
    const witness=obs.some(o=>x.experiments.find(e=>e.id===o.experiment).kind==="intervention"&&
      ms.some(m=>m.predictions[o.experiment]!==keep[0].predictions[o.experiment]));
    if(witness){verdict="CONDITIONAL_MODEL_SELECTION";reason="DECLARED_INTERVENTION_DISCRIMINATED_CANDIDATES";}
    else reason="NO_DISCRIMINATING_INTERVENTION_OBSERVED";
  }else if(next===null){
    reason=used.length>=x.budget?"BUDGET_EXHAUSTED_OR_NO_DISTINGUISHING_TEST":"NON_IDENTIFIABLE_WITHIN_PROTOCOL";
  }
  return {...base,verdict,reason,survivors:keep.map(m=>m.id),excluded,used_experiments:used,next_intervention:next};
}
