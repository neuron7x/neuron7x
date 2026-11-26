import assert from "node:assert/strict";
import test from "node:test";
import { evaluateCase, oracle } from "../research/adaptivity/evaluate.mjs";
import { predictionAccess, scoreTrace } from "../research/adaptivity/policies.mjs";

const rows = values => values.map(row => [...row]);
const selected = records => records.filter(record => record.selected).length;

test("exact policy reaches the categorical adaptive optimum and fixed pair cannot follow outcomes", () => {
  const {bound, policies} = evaluateCase(rows(["000", "010", "101", "102", "100"]));
  assert.equal(bound, 5);
  assert.equal(selected(policies.fixed), 3);
  assert.equal(selected(policies.pairs), 3);
  assert.equal(selected(policies.singleton), 3);
  assert.ok(policies.fixed.every(trial =>
    JSON.stringify(trial.fixed) === JSON.stringify(policies.fixed[0].fixed)));
  assert.throws(() => scoreTrace(rows(["000", "010", "101"]), 0, [0,2], ["0","1"]),
    /FIXED_POLICY_CHANGED/);
});

test("single-probe saturation and duplicate physical hypotheses are distinguished", () => {
  const saturated = evaluateCase(rows(["00", "10", "20"]));
  assert.equal(saturated.bound, 3);
  for (const trials of Object.values(saturated.policies)) {
    assert.ok(trials.every(trial => trial.trace.length === 1 && trial.selected));
  }
  const duplicates = evaluateCase(rows(["00", "00", "00"]));
  assert.equal(duplicates.bound, 0);
  assert.ok(Object.values(duplicates.policies).every(trials => selected(trials) === 0));
});

test("equal marginals can require disjoint first actions", () => {
  const left = rows(["0000","0001","0010","0011","0100","1101"]);
  const right = rows(["0000","0001","0010","0100","0101","1011"]);
  const marginals = matrix => [0,1,2,3].map(i => matrix.filter(row => row[i] === "1").length);
  assert.deepEqual(marginals(left), marginals(right));
  assert.deepEqual(oracle(left, 4), [2,2,3,2]);
  assert.deepEqual(oracle(right, 4), [2,3,2,2]);
  for (const [matrix, root] of [[left, 2], [right, 1]]) {
    assert.ok(evaluateCase(matrix).policies.exact.every(trial => trial.trace[0] === root));
  }
});

test("meter denies the sealed column and the 385th prediction access", () => {
  const matrix = rows(Array(8).fill("0000000"));
  const meter = predictionAccess(matrix);
  assert.deepEqual(meter.costs(), {reads:48, accesses:48});
  assert.throws(() => meter.models[0].predictions["6"], /PROBE_OUTSIDE_BUDGET/);
  for (let i = 48; i < 384; i++) assert.equal(meter.models[0].predictions["0"], "0");
  assert.throws(() => meter.models[0].predictions["0"], /PLANNING_BUDGET_EXCEEDED/);
  assert.throws(() => scoreTrace(matrix, 0, [6], null), /INVALID_TRACE/);
  assert.throws(() => scoreTrace(matrix, 0, [0,0], null), /INVALID_TRACE/);
});

test("sealed outcomes change oracle regret without changing any policy", () => {
  const left = rows(Array(8).fill("0000000"));
  const right = rows(Array.from({length:8}, (_, i) => "000000"+i));
  const cold = evaluateCase(left), revealed = evaluateCase(right);
  assert.deepEqual(cold.policies, revealed.policies);
  assert.equal(cold.fullBound, 0);
  assert.equal(revealed.fullBound, 8);
});
