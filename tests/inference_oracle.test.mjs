import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { EXACT_TWO_STEP, infer, PROTOCOL } from "../inference/kernel.mjs";

const atlas = JSON.parse(readFileSync(new URL("../research/atlas.json", import.meta.url), "utf8"));
const { slug: project, commit } = atlas.projects.find(entry => entry.slug === "cwc");

function survivors(models, observations) {
  return models.filter(model => observations.every(record =>
    model.predictions[record.experiment] === record.outcome));
}

// Recompute consistency and the recorded witness from the hypothetical history.
// Enumerate trees depth-first under the same unit cost, with stopping as a choice.
function oracle(models, observations, available, active, horizon) {
  const viable = survivors(models, observations);
  if (viable.length === 1 && observations.some(record =>
    active.includes(record.experiment) && models.some(model =>
      model.predictions[record.experiment] !== viable[0].predictions[record.experiment]))) {
    return { selections: 1, uses: 0, next: null };
  }
  let best = { selections: 0, uses: 0, next: null };
  if (horizon === 0 || viable.length === 0) return best;
  for (const experiment of available) {
    const outcomes = new Set(viable.map(model => model.predictions[experiment]));
    const unused = available.filter(id => id !== experiment);
    let selections = 0;
    let uses = viable.length;
    for (const outcome of outcomes) {
      const history = [...observations, { experiment, outcome }];
      const branch = oracle(models, history, unused, active, horizon - 1);
      selections += branch.selections;
      uses += branch.uses;
    }
    if (selections > best.selections || (selections === best.selections && uses < best.uses)) {
      best = { selections, uses, next: experiment };
    }
  }
  return best;
}

function compare(input, active) {
  const available = active.filter(id => !input.observations.some(record => record.experiment === id));
  const horizon = Math.min(2, input.budget - input.observations.length, available.length);
  const expected = oracle(input.models, input.observations, available, active, horizon);
  const viable = survivors(input.models, input.observations);
  const recorded = oracle(input.models, input.observations, available, active, 0);
  const verdict = viable.length === 0 ? "MODEL_CLASS_REFUTED"
    : recorded.selections === 1 ? "CONDITIONAL_MODEL_SELECTION" : "ABSTAIN";
  const actual = infer(input, atlas, EXACT_TWO_STEP);
  const state = input.case_id + " " + JSON.stringify(input.observations);
  assert.equal(actual.verdict, verdict, state);
  assert.deepEqual(actual.survivors, viable.map(model => model.id).sort(), state);
  assert.equal(actual.next_intervention, expected.next, state);
  assert.deepEqual(actual.intervention_plan, {
    horizon, selected_models: expected.selections, intervention_uses: expected.uses,
  }, state);
  assert.equal(actual.causal_authority, false, state);
  assert.equal(actual.independent_replication, false, state);
  return { actual, viable, available };
}

test("categorical plans and replayed decisions agree with an independent tree search", t => {
  let seed = 176588;
  function draw(range) {
    seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
    return (seed >>> 8) % range;
  }
  const categories = ["0", "1", "2", "constructor", "__proto__", "toString"];
  let decisions = 0;
  let rollouts = 0;

  for (let trial = 0; trial < 768; trial++) {
    const active = [..."ABCDEFG"].slice(0, 1 + draw(7));
    const ids = ["observe", ...active];
    const categoryCount = 2 + draw(categories.length - 1);
    const models = Array.from({ length: 2 + draw(7) }, (_, index) => ({
      id: "M" + index,
      predictions: Object.fromEntries(ids.map(id => [id, categories[draw(categoryCount)]])),
    })).reverse();
    const target = models[draw(models.length)];
    const observations = ids.filter(() => draw(4) === 0).map(experiment => ({
      experiment, outcome: draw(8) === 0 ? "OTHER" : target.predictions[experiment],
    })).reverse();
    const input = {
      schema: PROTOCOL,
      case_id: "oracle:" + trial,
      basis: trial % 2 === 0 ? "synthetic" : "unverified_external",
      source: { project, commit },
      budget: Math.max(1, observations.length + draw(7)),
      experiments: ids.map(id => ({
        id, kind: id === "observe" ? "observation" : "intervention",
      })).reverse(),
      models,
      observations,
    };
    const { actual, viable, available } = compare(input, active);
    decisions++;
    let selections = 0;
    let uses = 0;
    for (const model of viable) {
      const history = [...observations];
      let result = actual;
      while (result.next_intervention !== null) {
        const experiment = result.next_intervention;
        assert.ok(history.length < input.budget);
        assert.ok(!history.some(record => record.experiment === experiment));
        history.push({ experiment, outcome: model.predictions[experiment] });
        result = compare({ ...input, observations: history }, active).actual;
        decisions++;
        uses++;
      }
      assert.ok(result.survivors.includes(model.id));
      selections += Number(result.verdict === "CONDITIONAL_MODEL_SELECTION");
      rollouts++;
    }
    if (input.budget - observations.length <= 2 || available.length <= 2) {
      assert.equal(selections, actual.intervention_plan.selected_models, input.case_id);
      assert.equal(uses, actual.intervention_plan.intervention_uses, input.case_id);
    }
  }
  t.diagnostic(JSON.stringify({ decisions, rollouts }));
});
