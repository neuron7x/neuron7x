import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { EXACT_CLASS_TWO_STEP, EXACT_TWO_STEP, infer } from "../inference/kernel.mjs";

const read = path => JSON.parse(readFileSync(new URL("../" + path, import.meta.url), "utf8"));
const atlas = read("research/atlas.json");
const ids = ["passive", "A", "B"];
const caseFor = (rows, observations = []) => ({
  ...read("inference/cases/passive_twins.json"),
  budget: 3,
  experiments: ids.map(id => ({ id, kind: id === "passive" ? "observation" : "intervention" })),
  models: rows.map((row, index) => ({
    id: "M" + index, predictions: Object.fromEntries(ids.map((id, position) => [id, row[position]])),
  })),
  observations,
});
const append = (input, experiment, outcome) => ({
  ...input, observations: [...input.observations, { experiment, outcome }],
});

test("passive and unobserved intervention columns remain part of behavioral identity", () => {
  const passive = caseFor(["000", "100"], [
    { experiment: "passive", outcome: "0" }, { experiment: "A", outcome: "0" },
  ]);
  const singleton = infer(passive, atlas, EXACT_CLASS_TWO_STEP);
  assert.deepEqual(singleton.behavior_classes, { declared: 2, surviving: 1 });
  assert.equal(singleton.verdict, "ABSTAIN");
  assert.equal(singleton.next_intervention, null);

  const input = caseFor(["000", "000", "001", "010"], [
    { experiment: "passive", outcome: "0" }, { experiment: "A", outcome: "0" },
  ]);
  const prior = infer(input, atlas, EXACT_CLASS_TWO_STEP);
  assert.deepEqual(prior.behavior_classes, { declared: 3, surviving: 2 });
  assert.equal(prior.verdict, "ABSTAIN");
  assert.equal(prior.next_intervention, "B");
  const result = infer(append(input, "B", "0"), atlas, EXACT_CLASS_TWO_STEP);
  assert.equal(result.verdict, "CONDITIONAL_BEHAVIOR_CLASS_SELECTION");
  assert.deepEqual(result.survivors, ["M0", "M1"]);
});

test("a recorded active witness can distinguish a class from an already excluded rival", () => {
  const input = caseFor(["000", "000", "110"], [{ experiment: "passive", outcome: "0" }]);
  const prior = infer(input, atlas, EXACT_CLASS_TWO_STEP);
  assert.equal(prior.verdict, "ABSTAIN");
  assert.equal(prior.next_intervention, "A");
  const result = infer(append(input, "A", "0"), atlas, EXACT_CLASS_TWO_STEP);
  assert.equal(result.verdict, "CONDITIONAL_BEHAVIOR_CLASS_SELECTION");
  assert.deepEqual(result.survivors, ["M0", "M1"]);
  assert.equal(result.causal_authority, false);
  assert.equal(result.independent_replication, false);
});

test("class planning survives aliases and permutation across the complete three-row binary corpus", t => {
  const vectors = Array.from({ length: 8 }, (_, n) => n.toString(2).padStart(3, "0"));
  let states = 0;
  for (let a = 0; a < vectors.length; a++) {
    for (let b = a + 1; b < vectors.length; b++) {
      for (let c = b + 1; c < vectors.length; c++) {
        const base = caseFor([vectors[a], vectors[b], vectors[c]]);
        for (const actual of base.models) {
          const history = append(base, "passive", actual.predictions.passive);
          const aliased = {
            ...history,
            experiments: history.experiments.slice().reverse(),
            models: history.models.flatMap(model => [model, {
              id: "Alias" + model.id,
              predictions: Object.fromEntries(Object.entries(model.predictions).reverse()),
            }]).reverse(),
          };
          const row = infer(history, atlas, EXACT_TWO_STEP);
          const grouped = infer(aliased, atlas, EXACT_CLASS_TWO_STEP);
          assert.equal(grouped.next_intervention, row.next_intervention);
          assert.deepEqual(grouped.intervention_plan, {
            horizon: row.intervention_plan.horizon,
            selected_classes: row.intervention_plan.selected_models,
            intervention_uses: row.intervention_plan.intervention_uses,
          });
          assert.deepEqual(grouped.behavior_classes, { declared: 3, surviving: row.survivors.length });
          assert.deepEqual(grouped.survivors, [
            ...row.survivors.map(id => "Alias" + id), ...row.survivors,
          ]);
          assert.equal(grouped.verdict, "ABSTAIN");
          states++;
        }
      }
    }
  }
  assert.equal(states, 168);
  t.diagnostic(states + " passive histories preserve class plan and viable aliases");
});
