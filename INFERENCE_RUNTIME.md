# ⊛ Conditional Inference Gate

**Executable, finite-model epistemic discrimination.** Not a deployed autonomous cognitive agent, real-world causal authority, full CWC estimator, neural simulation, or independent replication.

## Runtime contract

Input defines a finite set of deterministic models, one passive observation channel, explicit admissible interventions, outcome records and an observation budget. Every model must predict every experiment. The kernel filters models consistent with supplied outcomes and returns a bounded verdict. The default intervention policy maximizes immediate pairwise separation. Choose `exact-two-step` when the objective is to obtain as many admissible conditional selections as possible within at most two further interventions.

- **ABSTAIN:** insufficient discrimination, synchronized mimickers, exhausted budget, or incorrect source reference.
- **CONDITIONAL_MODEL_SELECTION:** one survivor with a recorded intervention distinguishing it from the declared alternatives; **not proof of cause**.
- **CONDITIONAL_BEHAVIOR_CLASS_SELECTION:** one surviving equivalence class with a recorded discriminating intervention. The result lists every viable model ID in that class.
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

## Behavior classes and verified replay

Use `--exact-class-two-step` to give one vote to each distinct complete prediction vector, including the passive column. Predictions that agree on every declared experiment belong to the same class. Adding an alias to a class preserves the intervention policy within the case-size limit. The result reports `behavior_classes.declared`, `behavior_classes.surviving`, and `intervention_plan.selected_classes`. Equivalent IDs remain visible in `survivors`. The class verdict identifies their common declared behavior within the experiment set.

A receipt binds the declarations, ordered observation list, atlas, policy, forecast, verdict and evidence to SHA-256. Canonical inputs use UTF-8 JSON with sorted object keys and array order preserved. The evidence lists a record index and conflicting prediction for each excluded model. A selection includes the index of a recorded discriminating intervention. The forecast lists the next action for each modeled answer to the first intervention. An unmodeled answer may refute the class.

`--advance-receipt` verifies the previous receipt, requires exactly one appended observation for the prescribed action and keeps the original horizon. An independent `--receipt` call starts a new forecast and may select a different intervention from the committed continuation. Keep the original receipt or its digest separately if you need to detect replacement of the entire case and receipt together. Verification replays the supplied evidence and assumes that the caller has authenticated the records and atlas. It independently replays every modeled path of the emitted plan to check its selection and action counts. The finite planning oracle remains the independent test of optimality.

```sh
node tools/run_inference.mjs --receipt inference/cases/adaptive_categorical.json > receipt.json
node tools/run_inference.mjs --verify-receipt inference/cases/adaptive_categorical.json receipt.json
node tools/run_inference.mjs --advance-receipt prior-case.json receipt.json next-case.json > next-receipt.json
```

The first two commands use the same case. For the third, `prior-case.json` is the case underlying the receipt and `next-case.json` appends its recommended intervention and observed outcome. Use `--receipt-class` to start a class-based receipt.

- `--verify-anchored-receipt <case.json> <receipt.json> <trusted-sha256>` checks the regenerated receipt against an independently retained digest. This catches replacement of both files.
- `--verify-transition <prior-case.json> <prior-receipt.json> <new-case.json> <new-receipt.json> <trusted-prior-sha256>` authenticates the committed prefix against its anchor and verifies one successor. Several observed outcomes can produce valid successors. An independently retained successor digest distinguishes them.
- The JavaScript receipt API snapshots pure JSON values before replay. Accessors, proxies, sparse arrays and non-JSON values are rejected.

## Input and replay

The CLI accepts regular UTF-8 JSON files up to 64 KiB per case and 1 MiB for the local atlas. Duplicate decoded object keys are invalid. The atlas binds each project ID to one string commit SHA. `--check` compares the five baseline traces and the exact categorical trace byte-for-byte.

A case declares a time-invariant prediction for each model and intervention. The inference verdict treats records as a set. The receipt preserves their append order for audit. Cases that explicitly declare history dependence fail the v1 schema. Processes where earlier interventions change later responses require a separate prediction contract.

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
