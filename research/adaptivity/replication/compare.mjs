import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { evaluateCase } from "../evaluate.mjs";
import { ec2 } from "../ec2.mjs";

if (process.argv.length !== 3) throw Error("USAGE: node compare.mjs INPUT.json");
const raw = readFileSync(process.argv[2]);
const panel = JSON.parse(raw);
if (panel.schema !== "a02.inputs.v1" || panel.sources.length !== 11) throw Error("INVALID_PANEL");
const sources = panel.sources.map(({path, cases}) => ({
  path,
  cases: cases.map(({matrix}) => {
    if (matrix.length !== 8 || matrix.some(row => row.length !== 7 ||
      row.some(outcome => typeof outcome !== "string" || !/^[01]+$/.test(outcome)))) {
      throw Error("INVALID_MATRIX");
    }
    return {...evaluateCase(matrix), ec2: ec2(matrix)};
  }),
}));
console.log(JSON.stringify({schema:"a02.traces.v1",
  inputs_sha256:createHash("sha256").update(raw).digest("hex"), sources}));
