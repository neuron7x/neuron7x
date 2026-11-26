import { planTwoStep } from "../../inference/two_step_policy.mjs";

export function predictionAccess(matrix) {
  const n = matrix.length;
  const probes = Array.from({length: Math.min(6, matrix[0].length)}, (_, i) => String(i));
  const cache = Array.from({length: n}, () => new Map());
  let accesses = 0;
  let reads = 0;
  function read(row, probe) {
    if (!probes.includes(probe)) throw Error("PROBE_OUTSIDE_BUDGET");
    if (++accesses > 384) throw Error("PLANNING_BUDGET_EXCEEDED");
    if (!cache[row].has(probe)) {
      cache[row].set(probe, matrix[row][Number(probe)]);
      if (++reads > 48) throw Error("READ_BUDGET_EXCEEDED");
    }
    return cache[row].get(probe);
  }
  const informative = new Set();
  for (const probe of probes) {
    const first = read(0, probe);
    for (let row = 1; row < n; row++) {
      if (read(row, probe) !== first) informative.add(probe);
    }
  }
  const models = cache.map((_, row) => ({
    predictions: new Proxy({}, {
      get: (_, probe) => read(row, probe),
    }),
  }));
  return {models, probes, informative, costs: () => ({accesses, reads})};
}

function counts(signatures) {
  const result = new Map();
  for (const signature of signatures) result.set(signature, (result.get(signature) ?? 0) + 1);
  return [...result.values()];
}

function singles(values) {
  return values.filter(count => count === 1).length;
}

function greedy(models, probes, mode) {
  let best = null;
  let score = 0;
  for (const probe of probes) {
    const sizes = counts(models.map(model => model.predictions[probe]));
    if (sizes.length < 2) continue;
    const value = mode === "singleton" ? singles(sizes) :
      (models.length ** 2 - sizes.reduce((sum, size) => sum + size ** 2, 0)) / 2;
    if (best === null || value > score) {
      best = probe;
      score = value;
    }
  }
  return best;
}

function fixedPair(models, probes) {
  let best = [];
  let identified = 0;
  let uses = 0;
  for (const first of probes) {
    const observed = models.map(model => model.predictions[first]);
    const firstSingles = singles(counts(observed));
    for (const second of [null, ...probes.filter(probe => probe !== first)]) {
      const score = second === null ? firstSingles : singles(counts(models.map(
        (model, row) => JSON.stringify([observed[row], model.predictions[second]]))));
      const cost = models.length + (second === null ? 0 : models.length - firstSingles);
      if (score > identified || (score === identified && cost < uses)) {
        best = second === null ? [first] : [first, second];
        identified = score;
        uses = cost;
      }
    }
  }
  return best;
}

export function scoreTrace(matrix, truth, trace, fixed) {
  if (trace.length > 2 || new Set(trace).size !== trace.length ||
      trace.some(probe => !Number.isInteger(probe) || probe < 0 ||
        probe >= Math.min(6, matrix[0].length))) throw Error("INVALID_TRACE");
  if (fixed && trace.some((probe, i) => String(probe) !== fixed[i])) {
    throw Error("FIXED_POLICY_CHANGED");
  }
  const matching = matrix.flatMap((row, index) => trace.every(
    probe => row[probe] === matrix[truth][probe]) ? [index] : []);
  if (!matching.includes(truth)) throw Error("INVALID_SELECTION");
  return trace.length > 0 && matching.length === 1;
}

function evaluateTruth(matrix, truth, name) {
  const meter = predictionAccess(matrix);
  const {models, probes, informative} = meter;
  const trace = [];
  let viable = models;
  const fixed = name === "fixed" ? fixedPair(models, probes) : null;
  for (let step = 0; step < 2; step++) {
    const available = probes.filter(probe => !trace.includes(Number(probe)));
    const witness = trace.some(probe => informative.has(String(probe)));
    const probe = name === "exact" ? planTwoStep(viable, available, informative, 2-step, witness).next :
      fixed ? (fixed[step] ?? null) : greedy(viable, available, name);
    if (probe === null) break;
    const index = Number(probe);
    const outcome = matrix[truth][index];
    trace.push(index);
    if (step === 1) break;
    viable = viable.filter(model => model.predictions[probe] === outcome);
    if (viable.length === 1) break;
  }
  return {trace, fixed: fixed?.map(Number) ?? null,
    selected: scoreTrace(matrix, truth, trace, fixed), ...meter.costs()};
}

export function evaluate(matrix) {
  return Object.fromEntries(["exact", "fixed", "pairs", "singleton"].map(name =>
    [name, matrix.map((_, truth) => evaluateTruth(matrix, truth, name))]));
}
