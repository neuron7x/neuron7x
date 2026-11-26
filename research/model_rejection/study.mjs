// A06. Signed-off study protocol lives alongside this implementation.
const TRUTHS = Array.from({length: 16}, (_, signature) => signature);
const PROBES = [0, 1, 2, 3];
const STOP = -1;
const read = (signature, probe) => signature >> probe & 1;

function* trees() {
  yield [STOP, STOP, STOP];
  for (const root of PROBES) {
    const options = [STOP, ...PROBES.filter(probe => probe !== root)];
    for (const left of options) for (const right of options) yield [root, left, right];
  }
}

function* catalogs() {
  for (let a = 0; a < 13; a++) for (let b = a+1; b < 14; b++) {
    for (let c = b+1; c < 15; c++) for (let d = c+1; d < 16; d++) yield [a,b,c,d];
  }
}

function path(signature, tree) {
  const [root, ...after] = tree;
  if (root === STOP) return [];
  const first = read(signature, root);
  const next = after[first];
  return next === STOP ? [first] : [first, read(signature, next)];
}

// Projection evaluator builds transcript partitions before inspecting individual trials.
function scoreByProjection(catalog, tree, paths = TRUTHS.map(truth => path(truth, tree))) {
  const bins = new Map();
  for (const truth of catalog) {
    const key = paths[truth].join("");
    bins.set(key, (bins.get(key) ?? 0) + 1);
  }
  const score = {correct:0, false:0, rejected:0, insideUses:0, outsideUses:0};
  const declared = new Set(catalog);
  for (const truth of TRUTHS) {
    const observed = paths[truth];
    const matches = bins.get(observed.join("")) ?? 0;
    if (declared.has(truth)) {
      score.insideUses += observed.length;
      if (matches === 1 && observed.length) score.correct++;
    } else {
      score.outsideUses += observed.length;
      if (matches === 1 && observed.length) score.false++;
      if (!matches) score.rejected++;
    }
  }
  return score;
}

// Oracle traverses one observation at a time and drops inconsistent rows.
function observe(catalog, [root, negative, positive], truth) {
  let available = catalog;
  let probes = 0;
  for (let next = root; next !== STOP && probes < 2;) {
    const outcome = (truth & (1 << next)) === 0 ? 0 : 1;
    available = available.filter(candidate =>
      ((candidate & (1 << next)) === 0) === (outcome === 0));
    probes++;
    next = outcome ? positive : negative;
  }
  return {label: !available.length ? "refute" :
    probes && available.length === 1 ? available[0] : "abstain", probes};
}

function scoreByReplay(catalog, tree) {
  const score = {correct:0, false:0, rejected:0, insideUses:0, outsideUses:0};
  for (let truth = 0; truth < 16; truth++) {
    const {label, probes} = observe(catalog, tree, truth);
    if (catalog.includes(truth)) {
      score.insideUses += probes;
      if (label === truth) score.correct++;
      else if (label !== "abstain") throw Error("IN_CATALOG_WRONG_SELECTION");
    } else {
      score.outsideUses += probes;
      if (label === "refute") score.rejected++;
      else if (typeof label === "number") score.false++;
    }
  }
  return score;
}

const FIELDS = ["correct", "false", "rejected", "insideUses", "outsideUses"];
const empty = () => Object.fromEntries(FIELDS.map(field => [field, 0]));

function better(candidate, incumbent, rejects) {
  if (!incumbent || candidate.correct !== incumbent.correct) {
    return !incumbent || candidate.correct > incumbent.correct;
  }
  if (rejects && candidate.false !== incumbent.false) return candidate.false < incumbent.false;
  return candidate.insideUses < incumbent.insideUses;
}

function run() {
  const candidates = [...trees()].map(tree => [tree, TRUTHS.map(truth => path(truth, tree))]);
  const baseline = empty(), guarded = empty(), records = [];
  let treeChecks = 0;
  for (const catalog of catalogs()) {
    let base, guard, baseTree, guardTree;
    for (const [tree, paths] of candidates) {
      const score = scoreByProjection(catalog, tree, paths);
      const independent = scoreByReplay(catalog, tree);
      if (!FIELDS.every(key => score[key] === independent[key])) throw Error("ORACLE_DISAGREES");
      treeChecks++;
      if (better(score, base, false)) { base = score; baseTree = tree; }
      if (better(score, guard, true)) { guard = score; guardTree = tree; }
    }
    if (base.correct !== guard.correct || base.false < guard.false) throw Error("INVALID_COMPARISON");
    for (const field of FIELDS) {
      baseline[field] += base[field];
      guarded[field] += guard[field];
    }
    records.push({catalog, baseTree, guardTree, base, guard});
  }
  const inside = records.length * 4, outside = records.length * 12;
  const reducedFalse = baseline.false - guarded.false;
  const extraInsideUses = guarded.insideUses - baseline.insideUses;
  return {schema:"a06.catalog-rejection.v1", protocol:"3167c9e0a2d37df1499894f25816c7b0b67ad40e",
    catalogs:records.length, trees:candidates.length, treeChecks, inside, outside,
    improvedCatalogs:records.filter(({base,guard}) => base.false > guard.false).length,
    baseline, guarded, reducedFalse, extraInsideUses,
    decision: reducedFalse*10 >= outside && extraInsideUses*2 <= inside ? "PASS" : "REFUTED",
    records};
}

export {observe, run, scoreByProjection, scoreByReplay};
