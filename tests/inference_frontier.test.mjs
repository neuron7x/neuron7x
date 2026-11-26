import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import {observe, run as a06} from "../research/model_rejection/study.mjs";
import {assessCatalog, frontier, run} from "../research/inference_frontier/study.mjs";

const saved = JSON.parse(readFileSync(new URL("../research/inference_frontier/summary.json", import.meta.url)));

test("A07 and A08 reproduce all catalogs, all risk laws and the A06 coverage anchor", () => {
  const {records, ...results} = run(a06());
  assert.deepEqual(results, saved);
  assert.equal(records.length, 1820);
  for (const row of records) {
    const closed = row.frontiers[1].length-1;
    if (closed === 4) assert.equal(row.weighted.improvedPairs, 0);
  }
});

test("uniform outside signatures realize the full-depth leaf bound", () => {
  const catalog = [0,1,2,3];
  assert.deepEqual(frontier(15,1), [0]);
  assert.deepEqual(frontier(15,2), [0,3,6,9,12]);
  assert.deepEqual(frontier(15,3), [0,1,2,3,4]);
  assert.deepEqual(frontier(15,4), [0,0,0,0,0]);
  const tree = [0,1,1];
  const rejectedOutside = Array.from({length:16}, (_, i) => i).filter(truth =>
    !catalog.includes(truth) && typeof observe(catalog, tree, truth).label === "number");
  assert.equal(rejectedOutside.length, frontier(15,2).at(-1));
});

test("local fault weights improve a specific case and relabeling preserves the optimum", () => {
  const catalog = [0,1,4,8], weights = [8,4,2,1];
  const expected = assessCatalog(catalog, weights);
  assert.deepEqual(expected, {closed:2, baseline:26, least:20, mass:38});
  const reversed = catalog.map(truth =>
    [0,1,2,3].reduce((value, p) => value | ((truth >>> p) & 1) << (3-p), 0))
    .sort((a,b) => a-b);
  const relabeled = assessCatalog(reversed, [...weights].reverse());
  for (const field of ["closed","least","mass"]) assert.equal(relabeled[field], expected[field]);
});
