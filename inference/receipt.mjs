import { createHash } from "node:crypto";
import { types } from "node:util";
import { EXACT_CLASS_TWO_STEP, EXACT_TWO_STEP, infer, validate } from "./kernel.mjs";

const SCHEMA = "neuron7x.inference-receipt.v1";
const RECEIPT_HASH = /^[0-9a-f]{64}$/;

// Canonical representation for this version: sort object keys, preserve array order.
function canonical(value, depth = 0) {
  if (depth > 64 || types.isProxy(value)) throw Error("INVALID_RECEIPT_VALUE");
  if (value === null || typeof value === "string" || typeof value === "boolean" || Number.isFinite(value)) {
    return JSON.stringify(value);
  }
  if (typeof value !== "object") throw Error("INVALID_RECEIPT_VALUE");
  const array = Array.isArray(value);
  if (!array && ![Object.prototype, null].includes(Object.getPrototypeOf(value))) {
    throw Error("INVALID_RECEIPT_VALUE");
  }
  const descriptors = Object.getOwnPropertyDescriptors(value);
  const keys = Reflect.ownKeys(descriptors).filter(key => !(array && key === "length"));
  if (array && keys.length !== value.length) throw Error("INVALID_RECEIPT_VALUE");
  if (keys.some(key => typeof key !== "string")) throw Error("INVALID_RECEIPT_VALUE");

  const names = array ? Array.from({ length: value.length }, (_, index) => String(index)) : keys.sort();
  const encoded = names.map(key => {
    if (!Object.hasOwn(descriptors, key)) throw Error("INVALID_RECEIPT_VALUE");
    const property = descriptors[key];
    if (!property.enumerable || !Object.hasOwn(property, "value")) throw Error("INVALID_RECEIPT_VALUE");
    const entry = canonical(property.value, depth + 1);
    return array ? entry : JSON.stringify(key) + ":" + entry;
  }).join(",");
  return array ? "[" + encoded + "]" : "{" + encoded + "}";
}

const snapshot = value => JSON.parse(canonical(value));
const digest = value => createHash("sha256").update(canonical(value), "utf8").digest("hex");

function declaration(input) {
  const { observations, ...declared } = input;
  return declared;
}

function distinctBehaviors(models, columns) {
  const representatives = [];
  for (const model of models) {
    if (!representatives.some(other => columns.every(id => other.predictions[id] === model.predictions[id]))) {
      representatives.push(model);
    }
  }
  return representatives;
}

function targets(input, survivors, policy) {
  return policy === EXACT_CLASS_TWO_STEP
    ? distinctBehaviors(survivors, input.experiments.map(entry => entry.id))
    : survivors;
}

function observedEvidence(input, result, policy) {
  const active = new Set(input.experiments.filter(entry => entry.kind === "intervention").map(entry => entry.id));
  const models = [...input.models].sort((left, right) => left.id < right.id ? -1 : left.id === right.id ? 0 : 1);
  const survivors = [];
  const exclusions = [];
  for (const model of models) {
    const record = input.observations.findIndex(obs => obs.outcome !== model.predictions[obs.experiment]);
    if (record < 0) survivors.push(model);
    else exclusions.push({ model: model.id, record, predicted: model.predictions[input.observations[record].experiment] });
  }

  const witness = input.observations.findIndex(obs => active.has(obs.experiment)
    && models.some(model => model.predictions[obs.experiment] !== obs.outcome));
  const ids = survivors.map(model => model.id);
  const eligible = targets(input, survivors, policy).length === 1;
  const selection = policy === EXACT_CLASS_TWO_STEP ? "CONDITIONAL_BEHAVIOR_CLASS_SELECTION" : "CONDITIONAL_MODEL_SELECTION";
  const verdict = ids.length === 0 ? "MODEL_CLASS_REFUTED" : eligible && witness >= 0 ? selection : "ABSTAIN";
  if (result.verdict !== verdict || canonical(result.survivors) !== canonical(ids)
    || canonical(result.excluded) !== canonical(exclusions.map(item => item.model))
    || result.causal_authority !== false || result.independent_replication !== false) {
    throw Error("INVALID_INFERENCE_EVIDENCE");
  }
  return { exclusions, witness_record: verdict === selection ? witness : null };
}

function forecast(input, atlas, policy, initial) {
  const next = initial.next_intervention;
  const branches = [];
  if (next !== null && initial.intervention_plan.horizon === 2) {
    const viable = new Set(initial.survivors);
    const outcomes = new Set(input.models.filter(model => viable.has(model.id)).map(model => model.predictions[next]));
    for (const outcome of [...outcomes].sort()) {
      const branch = infer({
        ...input,
        budget: input.observations.length + 2,
        observations: [...input.observations, { experiment: next, outcome }],
      }, atlas, policy);
      branches.push({ outcome, next: branch.next_intervention });
    }
  }
  return { first: next, branches };
}

// Score the returned plan from raw predictions and records, without calling infer.
function verifyForecast(input, policy, result, plan, budget = input.budget) {
  const active = new Set(input.experiments.filter(entry => entry.kind === "intervention").map(entry => entry.id));
  const alreadyUsed = new Set(input.observations.map(obs => obs.experiment));
  const available = [...active].filter(action => !alreadyUsed.has(action)).length;
  const horizon = Math.min(2, budget - input.observations.length, available);
  if (result.intervention_plan.horizon !== horizon) throw Error("INVALID_INFERENCE_FORECAST");
  const fits = (model, records) => records.every(obs => model.predictions[obs.experiment] === obs.outcome);
  const viable = input.models.filter(model => fits(model, input.observations));
  let selected = 0;
  let uses = 0;
  for (const model of targets(input, viable, policy)) {
    const records = [...input.observations];
    function record(action) {
      if (!active.has(action) || alreadyUsed.has(action) || records.some(obs => obs.experiment === action)
        || records.length - input.observations.length >= result.intervention_plan.horizon) {
        throw Error("INVALID_INFERENCE_FORECAST");
      }
      records.push({ experiment: action, outcome: model.predictions[action] });
      uses++;
    }
    if (plan.first !== null) {
      record(plan.first);
      const second = plan.branches.find(branch => branch.outcome === model.predictions[plan.first])?.next;
      if (second != null) record(second);
    }
    const survivors = input.models.filter(candidate => fits(candidate, records));
    const witness = records.some(obs => active.has(obs.experiment)
      && input.models.some(candidate => candidate.predictions[obs.experiment] !== obs.outcome));
    if (witness && targets(input, survivors, policy).length === 1) selected++;
  }
  const advertised = policy === EXACT_CLASS_TWO_STEP
    ? result.intervention_plan.selected_classes
    : result.intervention_plan.selected_models;
  if (advertised !== selected || result.intervention_plan.intervention_uses !== uses) {
    throw Error("INVALID_INFERENCE_FORECAST");
  }
}

function receiptAt(input, atlas, policy, start) {
  if (policy !== EXACT_TWO_STEP && policy !== EXACT_CLASS_TWO_STEP) throw Error("INVALID_RECEIPT_POLICY");
  validate(input);
  if (!Number.isInteger(start) || start < 0 || start > input.observations.length) throw Error("INVALID_RECEIPT_PREFIX");

  const initial = { ...input, observations: input.observations.slice(0, start) };
  let result = infer(initial, atlas, policy);
  if (result.source_status !== "PINNED_REFERENCE_ONLY") throw Error("RECEIPT_SOURCE_MISMATCH");
  const budget = start + result.intervention_plan.horizon;
  const plan = forecast(initial, atlas, policy, result);
  observedEvidence(initial, result, policy);
  verifyForecast(initial, policy, result, plan);
  let next = plan.first;
  for (let index = start; index < input.observations.length; index++) {
    const event = input.observations[index];
    if (next === null || event.experiment !== next || index >= budget) throw Error("RECEIPT_PLAN_MISMATCH");
    next = index === start ? plan.branches.find(branch => branch.outcome === event.outcome)?.next ?? null : null;
    result = infer({ ...input, budget, observations: input.observations.slice(0, index + 1) }, atlas, policy);
    if (result.next_intervention !== next) throw Error("RECEIPT_PLAN_MISMATCH");
  }

  if (input.observations.length > start) {
    verifyForecast(input, policy, result, { first: next, branches: [] }, budget);
  }

  const body = {
    schema: SCHEMA,
    policy,
    start_records: start,
    declaration_sha256: digest(declaration(input)),
    records_sha256: digest(input.observations),
    atlas_sha256: digest(atlas),
    output_sha256: digest(result),
    forecast: plan,
    result,
    evidence: observedEvidence(input, result, policy),
  };
  return { ...body, receipt_sha256: digest(body) };
}

export function createReceipt(input, atlas, policy = EXACT_TWO_STEP) {
  const data = snapshot(input);
  validate(data);
  return receiptAt(data, snapshot(atlas), policy, data.observations.length);
}

function replayReceipt(input, atlas, receipt, expectedDigest) {
  if (!receipt || receipt.schema !== SCHEMA) throw Error("INVALID_RECEIPT");
  const replay = receiptAt(input, atlas, receipt.policy, receipt.start_records);
  if (canonical(replay) !== canonical(receipt)) throw Error("RECEIPT_MISMATCH");
  if (expectedDigest !== undefined) {
    if (typeof expectedDigest !== "string" || !RECEIPT_HASH.test(expectedDigest)) throw Error("INVALID_RECEIPT_ANCHOR");
    if (replay.receipt_sha256 !== expectedDigest) throw Error("RECEIPT_ANCHOR_MISMATCH");
  }
  return replay;
}

export function verifyReceipt(input, atlas, receipt, expectedDigest) {
  return replayReceipt(snapshot(input), snapshot(atlas), snapshot(receipt), expectedDigest);
}

export function advanceReceipt(previous, current, atlas, receipt, expectedDigest) {
  const prior = snapshot(previous);
  const data = snapshot(current);
  const pins = snapshot(atlas);
  const trusted = replayReceipt(prior, pins, snapshot(receipt), expectedDigest);
  validate(data);
  const length = prior.observations.length;
  if (digest(declaration(data)) !== trusted.declaration_sha256
    || data.observations.length !== length + 1
    || digest(data.observations.slice(0, length)) !== trusted.records_sha256) {
    throw Error("RECEIPT_HISTORY_MISMATCH");
  }
  return receiptAt(data, pins, trusted.policy, trusted.start_records);
}

export function verifyTransition(previous, current, atlas, priorReceipt, nextReceipt, priorDigest) {
  if (priorDigest === undefined) throw Error("INVALID_RECEIPT_ANCHOR");
  const expected = advanceReceipt(previous, current, atlas, priorReceipt, priorDigest);
  if (canonical(expected) !== canonical(nextReceipt)) throw Error("RECEIPT_TRANSITION_MISMATCH");
  return expected;
}
