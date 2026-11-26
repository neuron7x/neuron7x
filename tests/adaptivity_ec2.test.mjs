import assert from "node:assert/strict";
import test from "node:test";
import { ec2, remainingEdgeWeight } from "../research/adaptivity/ec2.mjs";
import { evaluate } from "../research/adaptivity/policies.mjs";

function* partitions(size, prefix = [0], largest = 0) {
  if (prefix.length === size) {
    yield prefix;
    return;
  }
  for (let value = 0; value <= largest + 1; value++) {
    yield* partitions(size, [...prefix, value], Math.max(largest, value));
  }
}

test("EC2 score matches direct conditional remaining-edge enumeration", () => {
  let verified = 0;
  for (let size = 2; size <= 8; size++) {
    for (const outcomes of partitions(size)) {
      let survivors = 0;
      for (const truth of outcomes) {
        for (let left = 0; left < size; left++) {
          for (let right = left + 1; right < size; right++) {
            survivors += Number(outcomes[left] === truth && outcomes[right] === truth);
          }
        }
      }
      assert.equal(remainingEdgeWeight(outcomes), 2 * survivors);
      verified++;
    }
  }
  assert.equal(verified, 5294);
});

test("EC2 and ordinary separated pairs choose different roots on 4/4 versus 5/2/1", () => {
  const matrix = Array.from({length:8}, (_, i) => [Number(i >= 4), i < 5 ? 0 : i < 7 ? 1 : 2]);
  assert.ok(ec2(matrix).every(result => result.trace[0] === 0));
  assert.ok(evaluate(matrix).pairs.every(result => result.trace[0] === 1));
});
