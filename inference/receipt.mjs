import { createHash } from "node:crypto";
import { EXACT_CLASS_TWO_STEP, EXACT_TWO_STEP, infer, validate } from "./kernel.mjs";

const SCHEMA = "neuron7x.inference-receipt.v1";

// Canonical representation for this version: sort object keys, preserve array order.
function canonical(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean" || Number.isFinite(value)) {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (typeof value !== "object") throw Error("INVALID_RECEIPT_VALUE");
  return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + canonical(value[key])).join(",") + "}";
}

const digest = value => createHash("sha256").update(canonical(value), "utf8").digest("hex");

function declaration(input) {
  const { observations, ...declared } = input;
  return declared;
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
  const alternatives = new Set(survivors.map(model => JSON.stringify(input.experiments.map(entry => model.predictions[entry.id]))));
  const eligible = policy === EXACT_CLASS_TWO_STEP ? alternatives.size === 1 : survivors.length === 1;
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

function receiptAt(input, atlas, policy, start) {
  if (policy !== EXACT_TWO_STEP && policy !== EXACT_CLASS_TWO_STEP) throw Error("INVALID_RECEIPT_POLICY");
  validate(input);
  if (!Number.isInteger(start) || start < 0 || start > input.observations.length) throw Error("INVALID_RECEIPT_PREFIX");

  const initial = { ...input, observations: input.observations.slice(0, start) };
  let result = infer(initial, atlas, policy);
  if (result.source_status !== "PINNED_REFERENCE_ONLY") throw Error("RECEIPT_SOURCE_MISMATCH");
  const budget = start + result.intervention_plan.horizon;
  const plan = forecast(initial, atlas, policy, result);
  let next = plan.first;
  for (let index = start; index < input.observations.length; index++) {
    const event = input.observations[index];
    if (next === null || event.experiment !== next || index >= budget) throw Error("RECEIPT_PLAN_MISMATCH");
    next = index === start ? plan.branches.find(branch => branch.outcome === event.outcome)?.next ?? null : null;
    result = infer({ ...input, budget, observations: input.observations.slice(0, index + 1) }, atlas, policy);
    if (result.next_intervention !== next) throw Error("RECEIPT_PLAN_MISMATCH");
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
  validate(input);
  return receiptAt(input, atlas, policy, input.observations.length);
}

export function verifyReceipt(input, atlas, receipt) {
  if (!receipt || receipt.schema !== SCHEMA) throw Error("INVALID_RECEIPT");
  const replay = receiptAt(input, atlas, receipt.policy, receipt.start_records);
  if (canonical(replay) !== canonical(receipt)) throw Error("RECEIPT_MISMATCH");
  return replay;
}

export function advanceReceipt(previous, current, atlas, receipt) {
  verifyReceipt(previous, atlas, receipt);
  validate(current);
  const length = previous.observations.length;
  if (digest(declaration(current)) !== receipt.declaration_sha256
    || current.observations.length !== length + 1
    || digest(current.observations.slice(0, length)) !== receipt.records_sha256) {
    throw Error("RECEIPT_HISTORY_MISMATCH");
  }
  return receiptAt(current, atlas, receipt.policy, receipt.start_records);
}
