# ⊛ Conditional Inference Gate

**Executable, finite-model epistemic discrimination.** Not a deployed autonomous cognitive agent, real-world causal authority, full CWC estimator, neural simulation, or independent replication.

## Runtime contract

Input defines a finite set of deterministic models, one passive observation channel, explicit admissible interventions, outcome records and an observation budget. Every model must predict every experiment. The kernel filters models consistent with supplied outcomes, proposes the untested intervention with the highest pairwise discrimination, and returns a bounded verdict.

- **ABSTAIN:** insufficient discrimination, synchronized mimickers, exhausted budget, or incorrect source reference.
- **CONDITIONAL_MODEL_SELECTION:** one survivor with a recorded intervention distinguishing it from the declared alternatives; **not proof of cause**.
- **MODEL_CLASS_REFUTED:** none of the declared candidates fits; this says nothing about unmodelled causes.
- **INVALID_INPUT:** a failed contract throws and must not authorize action.

Every result has causal_authority=false and independent_replication=false. Unresolved assumptions include candidate-class completeness, intervention fidelity, provenance of observations, and exogenous mimickers. Even an observed model selection is conditional on the supplied (possibly unverified) records.

**Atlas relation:** a matching source commit means PINNED_REFERENCE_ONLY. It never turns a test-file path into executed scientific evidence. Included cases are all SYNTHETIC and do not report actual findings from CWC, BN-Syn, GeoSync, KORPUS or neosynaptex.

## Run offline — no Actions, npm, cloud or tokens

    node tools/run_inference.mjs inference/cases/passive_twins.json
    node tools/run_inference.mjs inference/cases/interventional_split.json
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
