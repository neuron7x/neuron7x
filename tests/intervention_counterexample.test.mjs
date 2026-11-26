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
const makeModels = rows => rows.map((signature, index) => ({
  id: `M${index + 1}`,
  predictions: {
    observe: "0",
    ...Object.fromEntries(interventions.map((id, column) => [id, signature[column]])),
  },
}));

function greedyReplay(models, target) {
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
  const models = makeModels(signatures);
  assert.equal(new Set(signatures).size, models.length);
  let identified = 0;
  for (const target of models) {
    const { result, queries } = greedyReplay(models, target);
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

function* combinations(values, size, start = 0) {
  if (size === 0) {
    yield [];
    return;
  }
  for (let i = start; i <= values.length - size; i++) {
    for (const tail of combinations(values, size - 1, i + 1)) {
      yield [values[i], ...tail];
    }
  }
}

// Each tied choice may be resolved separately after each observed outcome.
function greedyCounts(candidates, remaining, budget) {
  if (candidates.length <= 1) {
    return { min: candidates.length, max: candidates.length, lex: candidates.length };
  }
  if (budget === 0 || remaining.length === 0) return { min: 0, max: 0, lex: 0 };

  const splits = remaining.map(id => {
    const zero = candidates.filter(model => model.predictions[id] === "0");
    const one = candidates.filter(model => model.predictions[id] === "1");
    return { id, zero, one, pairs: zero.length * one.length };
  });
  const bestScore = Math.max(...splits.map(split => split.pairs));
  if (bestScore === 0) return { min: 0, max: 0, lex: 0 };

  const totals = splits.filter(split => split.pairs === bestScore).map(({ id, zero, one }) => {
    const other = remaining.filter(candidate => candidate !== id);
    const left = greedyCounts(zero, other, budget - 1);
    const right = greedyCounts(one, other, budget - 1);
    return { min: left.min + right.min, max: left.max + right.max, lex: left.lex + right.lex };
  });
  return {
    min: Math.min(...totals.map(result => result.min)),
    max: Math.max(...totals.map(result => result.max)),
    lex: totals[0].lex,
  };
}

test("exhaustive six-model census separates forced deficits from tie effects", t => {
  const rows = Array.from({ length: 16 }, (_, value) => value.toString(2).padStart(4, "0"));
  const gaps = {};
  let forced = 0;
  let tieSensitive = 0;
  let alwaysOptimal = 0;
  for (const table of combinations(rows, 6)) {
    const models = makeModels(table);
    const oracle = optimalCount(models, interventions, 2);
    const { min, max, lex } = greedyCounts(models, interventions, 2);
    let selected = 0;
    for (const target of models) {
      const { result } = greedyReplay(models, target);
      if (result.verdict === "CONDITIONAL_MODEL_SELECTION") {
        assert.deepEqual(result.survivors, [target.id]);
        selected++;
      } else {
        assert.equal(result.verdict, "ABSTAIN");
        assert.ok(result.survivors.includes(target.id));
      }
    }
    assert.equal(selected, lex, table.join(","));
    assert.ok(min <= lex && lex <= max && max <= oracle, table.join(","));
    const deficit = oracle - selected;
    gaps[deficit] = (gaps[deficit] ?? 0) + 1;
    if (max < oracle) forced++;
    else if (min < oracle) tieSensitive++;
    else alwaysOptimal++;
  }
  const census = { gaps, forced, tieSensitive, alwaysOptimal };
  t.diagnostic(JSON.stringify(census));
  assert.equal(forced + tieSensitive + alwaysOptimal, 8008);
  assert.deepEqual(census, {
    gaps: { 0: 1832, 1: 6176 },
    forced: 5904,
    tieSensitive: 384,
    alwaysOptimal: 1720,
  });
});
