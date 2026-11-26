export const EXACT_TWO_STEP = "exact-two-step";

function partition(models, intervention) {
  const branches = new Map();
  for (const model of models) {
    const outcome = model.predictions[intervention];
    if (!branches.has(outcome)) branches.set(outcome, []);
    branches.get(outcome).push(model);
  }
  return branches.values();
}

function selected(models, witness) {
  return Number(models.length === 1 && witness);
}

function bestLastStep(models, interventions, first, informative, witness) {
  const stopping = selected(models, witness);
  if (stopping) return { selections: stopping, uses: 0 };

  let selections = 0;
  for (const second of interventions) {
    if (second === first) continue;
    const canWitness = witness || informative.has(second);
    let count = 0;
    for (const branch of partition(models, second)) count += selected(branch, canWitness);
    selections = Math.max(selections, count);
  }
  return { selections, uses: selections > 0 ? models.length : 0 };
}

// Interventions arrive in lexical order. Ties favor fewer total interventions,
// then the first identifier. Counts are summed over the currently viable models.
export function planTwoStep(models, interventions, informative, horizon, witness) {
  let best = { next: null, selections: selected(models, witness), uses: 0 };
  if (horizon === 0 || models.length === 0 || best.selections > 0) return best;

  for (const first of interventions) {
    const canWitness = witness || informative.has(first);
    let selections = 0;
    let uses = models.length;
    for (const branch of partition(models, first)) {
      if (horizon === 1) {
        selections += selected(branch, canWitness);
      } else {
        const last = bestLastStep(branch, interventions, first, informative, canWitness);
        selections += last.selections;
        uses += last.uses;
      }
    }

    if (selections > best.selections || (selections === best.selections && uses < best.uses)) {
      best = { next: first, selections, uses };
    }
  }
  return best;
}
