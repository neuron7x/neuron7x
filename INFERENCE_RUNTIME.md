# ⊛ Conditional Inference Gate

**Executable, finite-model epistemic discrimination.** Not a deployed autonomous cognitive agent, real-world causal authority, full CWC estimator, neural simulation, or independent replication.

## Runtime contract

Input defines a finite set of deterministic models, one passive observation channel, explicit admissible interventions, outcome records and an observation budget. Every model must predict every experiment. The kernel filters models consistent with supplied outcomes and returns a bounded verdict. The default intervention policy maximizes immediate pairwise separation. Choose `exact-two-step` when the objective is to obtain as many admissible conditional selections as possible within at most two further interventions.

- **ABSTAIN:** insufficient discrimination, synchronized mimickers, exhausted budget, or incorrect source reference.
- **CONDITIONAL_MODEL_SELECTION:** one survivor with a recorded intervention distinguishing it from the declared alternatives; **not proof of cause**.
- **MODEL_CLASS_REFUTED:** none of the declared candidates fits; this says nothing about unmodelled causes.
- **INVALID_INPUT:** a failed contract throws and must not authorize action.

Every result has causal_authority=false and independent_replication=false. Unresolved assumptions include candidate-class completeness, intervention fidelity, provenance of observations, and exogenous mimickers. Even an observed model selection is conditional on the supplied (possibly unverified) records.

**Atlas relation:** a matching source commit means PINNED_REFERENCE_ONLY. It never turns a test-file path into executed scientific evidence. Included cases are all SYNTHETIC and do not report actual findings from CWC, BN-Syn, GeoSync, KORPUS or neosynaptex.

## Exact intervention selection

Use `infer(caseData, atlas, "exact-two-step")` or the CLI flag below. The rule prioritizes the number of currently viable model rows that reach `CONDITIONAL_MODEL_SELECTION` under their declared predictions. Among equally successful plans, it minimizes the sum of intervention uses over those rows, then breaks remaining ties by lexical intervention ID. An identity counted in the plan is hypothetical. The verdict still depends on the supplied records.

For each available first intervention, partition the viable rows by predicted outcome. Score each branch by the best eligible second intervention or by stopping. Sum branch selections and intervention uses, then compare first interventions by that ordered objective. Branches can choose different second interventions. A single surviving row earns a selection only when a recorded or planned intervention distinguishes it from at least one original row. Enumerating first and second interventions this way gives the exact optimum in `O(mk²)` time for `m` declared rows and `k` interventions. Outcomes can have more than two categories.

The horizon is the smallest of two, the unused record budget and the number of unused interventions. The passive record also consumes budget. The policy recommends no intervention when the best plan yields zero selections in that horizon, even when a probe could narrow the class. With more than two available records the policy replans after each new observation. The initial forecast describes its evaluated two-step plan. End-to-end optimality applies to a run with at most two remaining records.

A pinned case includes `intervention_plan.horizon`, `selected_models` and `intervention_uses`. The counts weight each declared surviving row equally. Changing the declarations, including the multiplicity of equivalent rows, can change the objective. For an unpinned source, the planner supplies no forecast. A declaration of a behavioral program supplies predictions for the allowed interventions. Establishing that those interventions isolate a real mechanism requires evidence beyond the declarations.

The [categorical example](./inference/cases/adaptive_categorical.json) has five models. Pair-count greedy selects three within two steps. The exact policy chooses A, then B for outcome 0 or C for outcome 1, and conditionally selects all five.

## Input and replay

The CLI accepts regular UTF-8 JSON files up to 64 KiB per case and 1 MiB for the local atlas. Duplicate decoded object keys are invalid. The atlas binds each project ID to one string commit SHA. `--check` compares the five baseline traces and the exact categorical trace byte-for-byte.

A case declares a time-invariant prediction for each model and intervention. Record order carries no information. Replaying a plan requires the same declarations and an updated list of observations within budget. If an intervention can change the response to a later intervention, define a different model and experiment protocol for that history-dependent process.

## Run offline — no Actions, npm, cloud or tokens

    node tools/run_inference.mjs inference/cases/passive_twins.json
    node tools/run_inference.mjs inference/cases/interventional_split.json
    node tools/run_inference.mjs --exact-two-step inference/cases/adaptive_categorical.json
    node tools/run_inference.mjs --check
    node --test tests/inference_gate.test.mjs

## Falsification examples

| Case | Expected outcome | JSON trace |
| --- | --- | --- |
| Passive-equivalent twins | ABSTAIN, suggests an intervention | [Result](inference/results/passive_twins.json) |
| Discriminating intervention | CONDITIONAL_MODEL_SELECTION | [Result](inference/results/interventional_split.json) |
| Synchronized exogenous mimicker | ABSTAIN | [Result](inference/results/synchronized_mimicker.json) |
| Contradicted entire declared class | MODEL_CLASS_REFUTED | [Result](inference/results/model_class_refuted.json) |
| Only Git source references | ABSTAIN | [Result](inference/results/source_only.json) |

The module is a deliberately restrictive finite baseline. It does not estimate stochastic confidence, verify randomization/exclusion or identify causal effects. See the [CWC pinned regime-identifiability implementation](https://github.com/neuron7x/sapolsky-behave-layers/blob/f2396198749ee9cf2d51078cc890e299f51d4bd9/cwc/causal/regime_identifiability.py) for the related but distinct scientific work. Extension requires a new versioned contract with separately falsifiable assumptions.

**Preserved:** Original brain animation, Research Atlas and Epistemic Signal assets. This module operates locally without hosted execution. GitHub README links are documentation/navigation, not a live-running AI service.
