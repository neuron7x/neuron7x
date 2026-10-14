import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname,join,resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {ROLES,verify,render,images,distinct} from "../tools/render_epistemic_signal.mjs";
const root=resolve(dirname(fileURLToPath(import.meta.url)),"..");
const atlas=JSON.parse(readFileSync(join(root,"research/atlas.json"),"utf8"));
test("scope is source identity, not validation of claims",()=>{
 assert.equal(verify(atlas),atlas);
 assert.deepEqual(ROLES,["inspect","reproduce","falsify","boundary"]);
 assert.deepEqual(atlas.projects.map(distinct),[4,4,4,4,3]);
});
test("four theme/size variants are transparent and bounded",()=>{
 const all=images(atlas);assert.equal(Object.keys(all).length,4);
 for(const s of Object.values(all)){
  assert.match(s,/20 PINNED ROUTES · 19 DISTINCT FILES · NO EXPERIMENT CLAIM/);
  assert.equal((s.match(/data-role="falsify"/g)||[]).length,5);
  assert.equal((s.match(/data-shared-source="true"/g)||[]).length,1);
  assert.doesNotMatch(s,/<(?:script|foreignObject|animate|image|rect)\b/i);
  assert.match(s,/^<svg xmlns="http:\/\/www.w3.org\/2000\/svg"/);
 }
});
test("rendering is deterministic and commit-sensitive",()=>{
 const copy=JSON.parse(JSON.stringify(atlas));
 assert.equal(render(atlas,"dark"),render(copy,"dark"));
 copy.projects[0].commit="f".repeat(40);
 assert.notEqual(render(atlas,"dark"),render(copy,"dark"));
});
test("invalid evidence always fails closed",()=>{
 for(const change of [
  x=>delete x.projects[0].files.falsify,
  x=>x.projects[0].commit="invalid",
  x=>x.projects[1].files.reproduce.path="../unsafe",
  x=>x.projects[1].slug=x.projects[0].slug,
  x=>x.verification_scope="All tests passed"
 ]){
  const x=JSON.parse(JSON.stringify(atlas));change(x);assert.throws(()=>verify(x));
 }
 assert.throws(()=>render(atlas,"glow"));
});
test("brain animation remains explicitly unmodified in README",()=>{
 const content=readFileSync(join(root,"README.md"),"utf8");
 assert.match(content,/<img src="\.\/assets\/neuro-code\.webp" width="100%"/);
 assert.match(content,/\.\/assets\/epistemic-signal-mobile-dark\.svg/);
 assert.match(content,/\.\/assets\/epistemic-signal-light\.svg/);
});

test("eight nodes form two centered rows with bounded responsive geometry",()=>{
 const expanded=JSON.parse(JSON.stringify(atlas));
 for(let i=0;i<3;i++){
  const project=JSON.parse(JSON.stringify(expanded.projects[i]));
  project.slug="extension-"+i;
  project.name="Extended"+i;
  expanded.projects.push(project);
 }
 verify(expanded);
 const wide=render(expanded,"dark");
 const mobile=render(expanded,"light",true);
 assert.match(wide,/viewBox="0 0 1040 305"/);
 assert.match(mobile,/viewBox="0 0 500 305"/);
 assert.equal((wide.match(/data-project="/g)||[]).length,8);
 assert.equal((mobile.match(/data-project="/g)||[]).length,8);
 assert.match(wide,/32 PINNED ROUTES/);
});
