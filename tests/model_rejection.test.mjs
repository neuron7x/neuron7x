import assert from "node:assert/strict";
import test from "node:test";
import {readFileSync} from "node:fs";
import {observe, run} from "../research/model_rejection/study.mjs";

const saved = JSON.parse(readFileSync(new URL("../research/model_rejection/summary.json", import.meta.url)));

test("A06 exhaustive trajectories verify the frozen outcome", () => {
  const {records, ...actual} = run();
  assert.deepEqual(actual, saved);
  assert.equal(records.length, 1820);
  for (const {catalog, baseTree, guardTree, base, guard} of records) {
    assert.equal(base.correct, guard.correct);
    for (const [tree, score] of [[baseTree, base], [guardTree, guard]]) {
      // An identified row's leaf has 2^(4-depth) possible signatures.
      const unavoidable = catalog.reduce((sum, truth) => {
        const result = observe(catalog, tree, truth);
        return sum + (result.label === truth ? (2 ** (4 - result.probes) - 1) : 0);
      }, 0);
      assert.equal(score.false, unavoidable);
    }
    assert.equal(guard.false, 3 * guard.correct);
  }
});

test("a second probe can refute an initial singleton", () => {
  const catalog = [0, 1, 3, 5];
  assert.deepEqual(observe(catalog, [0,-1,-1], 2), {label:0, probes:1});
  assert.deepEqual(observe(catalog, [0,1,-1], 2), {label:"refute", probes:2});
  assert.deepEqual(observe(catalog, [0,1,-1], 0), {label:0, probes:2});
});

test("a differently named mechanism with the same signature shares the terminal label", () => {
  const known = {model:"declared", signature:0};
  const hidden = {model:"unseen mechanism", signature:0};
  const catalog = [0, 1, 3, 5];
  assert.notEqual(known.model, hidden.model);
  assert.deepEqual(observe(catalog, [0,1,-1], known.signature),
    observe(catalog, [0,1,-1], hidden.signature));
});
