import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { infer } from "../inference/kernel.mjs";

const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const atlas = read("../research/atlas.json");
const { source } = read("../inference/cases/passive_twins.json");
const interventions = ["A", "B", "C", "D"];
const signatures = ["0001", "0010", "0100", "1101", "1100", "1110"];
const experiments = [
  { id: "observe", kind: "observation" },
  ...interventions.map(id => ({ id, kind: "intervention" })),
];
const models = signatures.map((signature, index) => ({
  id: `M${index + 1}`,
  predictions: {
    observe: "0",
    ...Object.fromEntries(interventions.map((id, column) => [id, signature[column]])),
  },
}));

function greedyReplay(target) {
  const input = {
    schema: "neuron7x.conditional-inference.v1",
    case_id: "two_intervention_counterexample",
    basis: "synthetic",
    source,
    budget: 3,
    experiments,
    models,
    observations: [{ experiment: "observe", outcome: "0" }],
  };
  const queries = [];
  while (true) {
    const result = infer(input, atlas);
    assert.equal(result.causal_authority, false);
    assert.equal(result.independent_replication, false);
    if (!result.next_intervention) return { result, queries };
    const experiment = result.next_intervention;
    queries.push(experiment);
    input.observations.push({ experiment, outcome: target.predictions[experiment] });
  }
}

// Count singleton leaves in the best possible adaptive tree with the given budget.
function optimalCount(candidates, remaining, budget) {
  if (candidates.length <= 1) return candidates.length;
  if (budget === 0 || remaining.length === 0) return 0;
  return Math.max(...remaining.map(id => {
    const other = remaining.filter(candidate => candidate !== id);
    return ["0", "1"].reduce((total, outcome) => total +
      optimalCount(candidates.filter(model => model.predictions[id] === outcome), other, budget - 1), 0);
  }));
}

test("maximum immediate pair separation can lose identifications under a fixed budget", () => {
  assert.equal(new Set(signatures).size, models.length);
  let identified = 0;
  for (const target of models) {
    const { result, queries } = greedyReplay(target);
    assert.equal(queries[0], "A");
    assert.ok(queries.length <= 2);
    if (result.verdict === "CONDITIONAL_MODEL_SELECTION") {
      assert.deepEqual(result.survivors, [target.id]);
      identified++;
    } else {
      assert.equal(result.verdict, "ABSTAIN");
      assert.ok(result.survivors.includes(target.id));
    }
  }
  const oracle = optimalCount(models, interventions, 2);
  const fixed = new Set(models
    .map(model => model.predictions.B + model.predictions.C)
    .filter((signature, _, all) => all.indexOf(signature) === all.lastIndexOf(signature)));
  const fixedCount = fixed.size;
  assert.deepEqual([identified, fixedCount, oracle], [2, 3, 3]);
});
