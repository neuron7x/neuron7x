/**
 * NEURON7X / Epistemic Signal
 * Deterministic, offline, fail-closed visual index of pinned SOURCE references.
 * No experiment, model fidelity or readiness inferred.
 * Usage: node tools/render_epistemic_signal.mjs [--check]
 */
import {readFileSync,writeFileSync,mkdirSync} from "node:fs";
import {join,resolve,dirname} from "node:path";
import {fileURLToPath} from "node:url";
export const ROLES=["inspect","reproduce","falsify","boundary"];
export function escapeXml(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
export function fnv32(s){let h=2166136261;for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619)>>>0;return h>>>0}
export function distinct(p){return new Set(ROLES.map(r=>p.repository+"@"+p.commit+":"+p.files[r].blob)).size}
export function verify(m){
 if(m.schema!=="neuron7x.research-atlas.v1"||!Array.isArray(m.projects)||m.projects.length<1||m.projects.length>8)throw Error("Invalid schema or project count");
 if(!/^\d{4}-\d{2}-\d{2}$/.test(m.verified_date)||!/not executed/i.test(m.verification_scope||""))throw Error("Unsupported verification scope");
 const seen=new Set();
 for(const p of m.projects){
  if(!/^[a-z][a-z0-9-]*$/.test(p.slug)||seen.has(p.slug)||!p.name||p.name.length>24)throw Error("Invalid project identity");
  seen.add(p.slug);
  if(!/^neuron7x\/[A-Za-z0-9_.-]+$/.test(p.repository)||!/^[a-f0-9]{40}$/.test(p.commit))throw Error("Invalid source revision");
  if(Object.keys(p.files||{}).sort().join()!==[...ROLES].sort().join())throw Error("Incomplete evidence roles");
  for(const r of ROLES){
   const f=p.files[r];
   if(!f||!/^[a-f0-9]{40}$/.test(f.blob)||!f.path||f.path.startsWith("/")||f.path.split("/").includes(".."))throw Error("Unsafe source reference");
  }
 }
 return m;
}
export function render(m,theme,small=false){
 verify(m);
 if(!["dark","light"].includes(theme))throw Error("Unknown theme");
 const c=theme==="dark"?{fg:"#e6edf3",mid:"#a1aab5",thin:"#69737e",stroke:"#525e6b",red:"#ff625b"}:{fg:"#1f2328",mid:"#59636e",thin:"#6e7781",stroke:"#8d97a1",red:"#bd3346"};
 const W=small?500:1040,rows=Math.ceil(m.projects.length/5),H=181+(rows-1)*124,Y=99;
 const X=m.projects.map((_,i)=>{const row=Math.floor(i/5),count=Math.min(5,m.projects.length-row*5),gap=small?98:200;return (W-gap*(count-1))/2+(i%5)*gap});
 const CY=m.projects.map((_,i)=>Y+Math.floor(i/5)*124);
 const all=m.projects.flatMap(p=>ROLES.map(r=>p.repository+"@"+p.commit+":"+p.files[r].blob));
 const unique=new Set(all).size;
 const visualKey=fnv32(all.join("|")).toString(16).padStart(8,"0");
 const out=[
 `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="title description">`,
 `<title id="title">NEURON7X — Epistemic Signal</title>`,
 `<desc id="description">Five projects, four pinned source-reference routes each: inspect, reproduce, falsify and boundary. Shared source blobs have a bridge. ${unique} distinct source files. The curved lines are deterministic decorative identifiers, not observed neural dynamics. No experiments or independent replication were executed or confirmed by this visual index. Source snapshot ${escapeXml(m.verified_date)}.</desc>`,
 `<g font-family="Arial,DejaVu Sans,sans-serif">`,
 `<text x="${small?12:28}" y="23" fill="${c.fg}" font-size="${small?13:17}" font-weight="600" letter-spacing=".6">⊛ EPISTEMIC SIGNAL</text>`,
 `<text x="${W-(small?12:28)}" y="22" text-anchor="end" fill="${c.mid}" font-size="${small?9:11}">REF ${escapeXml(m.verified_date)} · ${visualKey}</text>`,
 `<path d="M ${small?12:28} 34 H ${W-(small?12:28)}" stroke="${c.stroke}" opacity=".65" stroke-width=".7"/>`
 ];
 for(let i=0;i<X.length-1;i++){
  if((i+1)%5===0)continue;
  const Y=CY[i];
  const a=X[i],b=X[i+1],v=(fnv32(m.projects[i].commit+m.projects[i+1].commit)%19-9)*(small?.65:1);
  out.push(`<path d="M ${a+17} ${Y} C ${a+(b-a)*.32} ${Y+v}, ${a+(b-a)*.68} ${Y-v}, ${b-17} ${Y}" fill="none" stroke="${c.stroke}" opacity=".72" stroke-width="1.2"/>`);
  out.push(`<path d="M ${a+17} ${Y+4} Q ${(a+b)/2} ${Y+8+v*.35}, ${b-17} ${Y+4}" fill="none" stroke="${c.red}" opacity=".25" stroke-width=".65"/>`);
 }
 const ports=[[0,-19],[19,0],[0,19],[-19,0]];
 for(let i=0;i<m.projects.length;i++){
  const p=m.projects[i],x=X[i],Y=CY[i],seed=fnv32(p.commit+ROLES.map(r=>p.files[r].blob).join(""));
  const shared=[];
  for(let a=0;a<4;a++)for(let b=a+1;b<4;b++)if(p.files[ROLES[a]].blob===p.files[ROLES[b]].blob)shared.push([a,b]);
  out.push(`<g data-project="${escapeXml(p.slug)}">`);
  out.push(`<text x="${x}" y="${Y-41}" text-anchor="middle" fill="${c.fg}" font-size="${small?10:15}" font-weight="600">${escapeXml(small?p.name.slice(0,11):p.name)}</text>`);
  out.push(`<circle cx="${x}" cy="${Y}" r="13" fill="none" stroke="${c.stroke}" stroke-width="1.2"/>`);
  out.push(`<path d="M ${x-10} ${Y-8} A 13 13 0 0 1 ${x+10} ${Y-8}" fill="none" stroke="${c.red}" stroke-width="1.2" opacity=".8" transform="rotate(${seed%45-22} ${x} ${Y})"/>`);
  out.push(`<circle cx="${x}" cy="${Y}" r="2.7" fill="${c.red}"/>`);
  for(let r=0;r<4;r++){const [dx,dy]=ports[r];out.push(`<circle data-role="${ROLES[r]}" cx="${x+dx}" cy="${Y+dy}" r="${small?2.5:3}" fill="${r===2?c.red:c.mid}"/>`);}
  for(const [a,b] of shared){const [ax,ay]=ports[a],[bx,by]=ports[b];out.push(`<path data-shared-source="true" d="M ${x+ax} ${Y+ay} Q ${x-27} ${Y-27}, ${x+bx} ${Y+by}" fill="none" stroke="${c.red}" stroke-width="1" stroke-dasharray="2 2"/>`);}
  out.push(`<text x="${x}" y="${Y+37}" text-anchor="middle" font-family="Consolas,DejaVu Sans Mono,monospace" font-size="${small?9:11}" fill="${c.mid}">${p.commit.slice(0,small?6:9)}</text>`);
  out.push(`<text x="${x}" y="${Y+52}" text-anchor="middle" font-size="${small?8:10}" fill="${c.thin}">${distinct(p)} SOURCES</text></g>`);
 }
 out.push(`<path d="M ${small?12:28} ${H-18} H ${W-(small?12:28)}" stroke="${c.stroke}" opacity=".6" stroke-width=".7"/>`);
 out.push(`<text x="${W/2}" y="${H-6}" text-anchor="middle" font-size="${small?8:11}" fill="${c.mid}">${all.length} PINNED ROUTES · ${unique} DISTINCT FILES · NO EXPERIMENT CLAIM</text></g></svg>`);
 return out.join("\n")+"\n";
}
export function images(m){const o={};for(const theme of ["dark","light"]){o[`assets/epistemic-signal-${theme}.svg`]=render(m,theme);o[`assets/epistemic-signal-mobile-${theme}.svg`]=render(m,theme,true);}return o;}
const root=resolve(dirname(fileURLToPath(import.meta.url)),"..");
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const args=process.argv.slice(2);
 if(args.length>1||args.some(a=>a!=="--check"))throw Error("Usage: node tools/render_epistemic_signal.mjs [--check]");
 const manifest=JSON.parse(readFileSync(join(root,"research/atlas.json"),"utf8"));
 const result=images(manifest);
 let failures=0;
 for(const [name,content] of Object.entries(result)){
  const path=join(root,name);
  if(args.includes("--check")){
   let observed=null;try{observed=readFileSync(path,"utf8")}catch{}
   if(observed!==content){console.error("OUT OF DATE:",name);failures++;}
  }else{
   mkdirSync(dirname(path),{recursive:true});
   writeFileSync(path,content,"utf8");
   console.log("GENERATED:",name);
  }
 }
 if(failures)process.exitCode=1;
 else console.log("EPISTEMIC SIGNAL: "+(args.includes("--check")?"CONSISTENT":"GENERATED")+"; no experiment claims");
}
