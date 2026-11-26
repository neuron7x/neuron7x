// Exact finite A07–A08 frontier. A06's reported coverage supplies the anchor.
const PROBES = [0, 1, 2, 3];
const FULL = 65535;
const SIZE = 16;
const bit = (truth, probe) => (truth >>> probe) & 1;
const ONES = PROBES.map(probe =>
  Array.from({length:SIZE}, (_, truth) => bit(truth, probe) << truth)
    .reduce((mask, entry) => mask | entry, 0));

function count(mask) {
  let size = 0;
  while (mask) { mask &= mask-1; size++; }
  return size;
}

function* combinations(values, needed, start = 0, prefix = []) {
  if (!needed) { yield prefix; return; }
  for (let i = start; i <= values.length-needed; i++) {
    yield* combinations(values, needed-1, i+1, [...prefix, values[i]]);
  }
}

function* permutations(values) {
  if (!values.length) { yield []; return; }
  for (const value of values) {
    for (const rest of permutations(values.filter(other => other !== value))) {
      yield [value, ...rest];
    }
  }
}

function put(frontier, correct, falseCount) {
  frontier[correct] = Math.min(frontier[correct] ?? Infinity, falseCount);
}

function frontier(catalogMask, horizon) {
  const cache = new Map();
  function solve(region, unread, left) {
    const key = region + (unread << 16) + (left << 20);
    if (cache.has(key)) return cache.get(key);
    const current = [0];
    if (count(region & catalogMask) === 1) current[1] = count(region) - 1;
    if (left > 0 && region & catalogMask) {
      for (const probe of PROBES) {
        const code = 1 << probe;
        if (!(unread & code)) continue;
        const yes = solve(region & ONES[probe], unread ^ code, left-1);
        const no = solve(region & ~ONES[probe], unread ^ code, left-1);
        for (const [a,n] of yes.entries()) {
          for (const [b,m] of no.entries()) put(current, a+b, n+m);
        }
      }
    }
    cache.set(key, current);
    return current;
  }
  return solve(FULL, 15, horizon);
}

function* trees() {
  for (const root of PROBES) {
    const rest = PROBES.filter(probe => probe !== root);
    for (const left of rest) for (const right of rest) yield [root,left,right];
  }
}

function traceModels(catalog, [root, left, right]) {
  const declared = new Set(catalog);
  const leaf = truth => {
    const first = bit(truth, root);
    return 2*first + bit(truth, first ? right : left);
  };
  const bins = [0,0,0,0];
  for (const truth of catalog) bins[leaf(truth)]++;
  const correct = bins.filter(size => size === 1).length;
  const flipCosts = PROBES.map(probe => catalog.filter(truth => {
    const changed = truth ^ (1 << probe);
    return !declared.has(changed) && bins[leaf(changed)] === 1;
  }).length);
  return {correct, flipCosts};
}

function branchOptions(catalogMask) {
  return PROBES.map(first => [0,1].map(outcome => {
    const branch = outcome ? ONES[first] : FULL ^ ONES[first];
    return PROBES.filter(second => second !== first).map(second => {
      const halves = [branch & ONES[second], branch & ~ONES[second]];
      const accepted = halves.filter(group => count(group & catalogMask) === 1);
      return [accepted.length, accepted.reduce((mask, group) => mask | (group & ~catalogMask), 0)];
    });
  }));
}

function threat(catalog, weights) {
  const masses = Array(SIZE).fill(0);
  const declared = new Set(catalog);
  for (const nominal of catalog) {
    for (const [probe, weight] of weights.entries()) {
      const changed = nominal ^ (1 << probe);
      if (!declared.has(changed)) masses[changed] += weight;
    }
  }
  return masses;
}

function sumMask(mask, masses) {
  let total = 0;
  while (mask) {
    const mark = mask & -mask;
    total += masses[31-Math.clz32(mark)];
    mask ^= mark;
  }
  return total;
}

function weightOptimal(roots, masses) {
  let bestCorrect = -1, least = Infinity;
  for (const branches of roots) {
    let correct = 0, cost = 0;
    for (const options of branches) {
      const branchCorrect = Math.max(...options.map(([capacity]) => capacity));
      correct += branchCorrect;
      cost += Math.min(...options.filter(([c]) => c === branchCorrect)
        .map(([,falseMask]) => sumMask(falseMask, masses)));
    }
    if (correct > bestCorrect || (correct === bestCorrect && cost < least)) {
      bestCorrect = correct;
      least = cost;
    }
  }
  return [bestCorrect, least];
}

function weightOracle(expected, weights) {
  return expected.flipCosts.reduce((total, hits, probe) => total + hits*weights[probe], 0);
}

function assessCatalog(catalog, weights) {
  const mask = catalog.reduce((combined, truth) => combined | (1 << truth), 0);
  const oracles = [...trees()].map(tree => traceModels(catalog, tree));
  const closed = Math.max(...oracles.map(result => result.correct));
  const eligible = oracles.filter(result => result.correct === closed);
  const roots = branchOptions(mask);
  const masses = threat(catalog, weights);
  const candidate = weightOptimal(roots, masses);
  const baseline = weightOracle(eligible[0], weights);
  const least = Math.min(...eligible.map(result => weightOracle(result, weights)));
  if (candidate[0] !== closed || candidate[1] !== least) throw Error("WEIGHTED_ORACLE_DISAGREES");
  return {closed, baseline, least, mass:masses.reduce((sum,w) => sum+w,0)};
}

function run(a06 = null) {
  const horizons = [1,2,3,4].map(h => ({h,maxCorrect:0,eligible:0,falseAtA06Coverage:0}));
  const weights = [...permutations([8,4,2,1])];
  const weighted = {baseline:0, optimized:0, mass:0, improvedPairs:0, pairs:0};
  const records = [];
  for (const catalog of combinations(Array.from({length:SIZE}, (_, i) => i), 4)) {
    const mask = catalog.reduce((sum, truth) => sum | (1 << truth), 0);
    const frontiers = horizons.map(({h}) => frontier(mask,h));
    for (const [index, costs] of frontiers.entries()) {
      if (!costs.every((cost, correct) => cost === (2 ** (3-index)-1)*correct)) {
        throw Error("LEAF_BOUND_DISAGREES");
      }
    }
    const record = {catalog, frontiers, weighted:{baseline:0,optimized:0,mass:0,improvedPairs:0,pairs:0}};
    const target = frontiers[1].length-1;
    if (a06 && (a06.records[records.length].catalog.join() !== catalog.join() ||
        a06.records[records.length].guard.correct !== target)) throw Error("A06_COVERAGE_DISAGREES");
    for (const [index, costs] of frontiers.entries()) {
      const policy = horizons[index];
      policy.maxCorrect += costs.length-1;
      if (costs[target] !== undefined) {
        policy.eligible++;
        policy.falseAtA06Coverage += costs[target];
      }
    }
    for (const permutation of weights) {
      const checked = assessCatalog(catalog, permutation);
      if (checked.closed !== target) throw Error("TWO_PROBE_ORACLE_DISAGREES");
      record.weighted.baseline += checked.baseline;
      record.weighted.optimized += checked.least;
      record.weighted.mass += checked.mass;
      record.weighted.improvedPairs += Number(checked.least < checked.baseline);
      record.weighted.pairs++;
    }
    for (const key of Object.keys(weighted)) weighted[key] += record.weighted[key];
    records.push(record);
  }
  const adequate = horizons.find(row => row.eligible === records.length &&
    row.falseAtA06Coverage*10 <= 12*records.length);
  const decision = (weighted.baseline-weighted.optimized)*10 >= weighted.baseline ? "PASS" : "REFUTED";
  return {schema:"a07-a08.v1",protocol:"20d7e3d02d7c2c682af4f25269b8f8da7cde148c",
    catalogs:records.length, horizons, minimumBudget:adequate?.h ?? null, weighted,decision,records};
}

export {assessCatalog,frontier,run};
