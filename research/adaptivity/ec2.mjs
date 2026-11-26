import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { predictionAccess, scoreTrace } from "./policies.mjs";

export function remainingEdgeWeight(outcomes) {
  const counts = new Map();
  for (const outcome of outcomes) counts.set(outcome, (counts.get(outcome) ?? 0) + 1);
  return [...counts.values()].reduce((value, size) => value + size * size * (size - 1), 0);
}

export function ec2(matrix) {
  return matrix.map((row, truth) => {
    const meter = predictionAccess(matrix);
    const trace = [];
    let viable = meter.models;
    while (trace.length < 2 && viable.length > 1) {
      let best = null;
      let score = viable.length ** 2 * (viable.length - 1);
      for (const probe of meter.probes) {
        if (trace.includes(Number(probe))) continue;
        const next = remainingEdgeWeight(viable.map(model => model.predictions[probe]));
        if (next < score) {
          best = probe;
          score = next;
        }
      }
      if (best === null) break;
      const index = Number(best);
      trace.push(index);
      if (trace.length === 1) {
        viable = viable.filter(model => model.predictions[best] === row[index]);
      }
    }
    return {trace, fixed: null, selected: scoreTrace(matrix, truth, trace, null), ...meter.costs()};
  });
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  if (process.argv.length !== 3) throw Error("USAGE: node ec2.mjs INPUT.json");
  const data = readFileSync(process.argv[2]);
  const inputs = JSON.parse(data);
  const result = inputs.sources.map(source => ({
    path: source.path,
    cases: source.cases.map(({matrix}) => ec2(matrix)),
  }));
  console.log(JSON.stringify({schema:"a01.ec2.v1",
    input_sha256:createHash("sha256").update(data).digest("hex"), result}));
}
