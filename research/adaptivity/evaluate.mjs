import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { evaluate } from "./policies.mjs";

// Sum success indicators by first observation. Each branch can choose its own
// second probe. Uniqueness is queried directly against every other hypothesis.
export function oracle(matrix, count) {
  const probes = Array.from({length: count}, (_, index) => index);
  return probes.map(first => {
    const outcomes = new Set(matrix.map(row => row[first]));
    let total = 0;
    for (const outcome of outcomes) {
      const same = matrix.filter(row => row[first] === outcome);
      if (same.length === 1) {
        total++;
      } else {
        total += Math.max(0, ...probes.filter(second => second !== first).map(second =>
          same.filter(row => same.every(other =>
            other === row || other[second] !== row[second])).length));
      }
    }
    return total;
  });
}

export function evaluateCase(matrix) {
  const policies = evaluate(matrix);
  const bound = Math.max(...oracle(matrix, Math.min(6, matrix[0].length)));
  const fullBound = Math.max(...oracle(matrix, matrix[0].length));
  const selections = rows => rows.filter(row => row.selected).length;
  if (selections(policies.exact) !== bound || bound > fullBound ||
      Object.values(policies).some(rows => selections(rows) > bound)) throw Error("ORACLE_DISAGREEMENT");
  return {bound, fullBound, policies};
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  if (process.argv.length !== 3) throw Error("USAGE: node evaluate.mjs INPUT.json");
  const data = readFileSync(process.argv[2]);
  const input = JSON.parse(data);
  if (input.schema !== "a01.inputs.v1" || input.sources.length !== 20 ||
      new Set(input.sources.map(source => source.path)).size !== 20 ||
      input.sources.some(source => source.cases.length !== 16)) throw Error("INCOMPLETE_PANEL");
  const result = input.sources.map(source => ({
    path: source.path,
    cases: source.cases.map(({matrix}) => {
      if (matrix.length !== 8 || matrix.some(row => row.length !== 7 ||
        row.some(outcome => typeof outcome !== "string" || !/^[01]+$/.test(outcome)))) {
        throw Error("INVALID_MATRIX");
      }
      return evaluateCase(matrix);
    }),
  }));
  console.log(JSON.stringify({schema: "a01.traces.v1",
    input_sha256: createHash("sha256").update(data).digest("hex"), result}));
}
