#!/usr/bin/env node
/** Offline inference CLI; no network or paid services. */
import {readFileSync} from "node:fs";
import {resolve,join,dirname} from "node:path";
import {fileURLToPath} from "node:url";
import {infer} from "../inference/kernel.mjs";
const root=resolve(dirname(fileURLToPath(import.meta.url)),"..");
const atlas=JSON.parse(readFileSync(join(root,"research/atlas.json"),"utf8"));
const names=["passive_twins","interventional_split","synchronized_mimicker","model_class_refuted","source_only"];
const argv=process.argv.slice(2);
function run(path){return JSON.stringify(infer(JSON.parse(readFileSync(path,"utf8")),atlas),null,2)+"\n";}
if(argv.length===1&&argv[0]==="--check"){
 let failures=0;
 for(const n of names){
  const actual=run(join(root,"inference/cases/"+n+".json"));
  const expected=readFileSync(join(root,"inference/results/"+n+".json"),"utf8");
  if(actual!==expected){console.error("SNAPSHOT_MISMATCH "+n);failures++;}
 }
 if(failures)process.exitCode=1;else console.log("INFERENCE_CONFORMANCE: 5/5 snapshots match");
}else if(argv.length===1&&!argv[0].startsWith("-")){
 process.stdout.write(run(resolve(argv[0])));
}else{
 console.error("Usage: node tools/run_inference.mjs --check | <local-case.json>");
 process.exitCode=2;
}
