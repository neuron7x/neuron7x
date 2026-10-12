# Research Evidence Atlas

A source-pinned route from a research mechanism to its reproduction guide, an adversarial probe or counterexample, and the limit of the resulting claim.

**Source snapshot:** 2026-10-12 · **Atlas fingerprint:** `6fc046f2545d955ea9617ef4726c27c42e9a5915601d17f7ba1e8ad008ae831d`

Source references and blob identities verified. Project test suites and experiments were not executed for this profile update.

**Navigate:** [CWC](#cwc) · [BN-Syn](#bnsyn) · [GeoSync](#geosync) · [neosynaptex](#neosynaptex) · [KORPUS](#korpus)

## Inspection protocol

1. **Inspect:** read the linked implementation and its assumptions.
2. **Reproduce:** check out the pinned commit and follow that project's environment and run guide. The linked probe is a specific inspection target, not the project's complete validation programme.
3. **Falsify:** use the adversarial test, property-based probe, or recorded counterexample; compare its scope with the claim boundary.
4. **Challenge:** submit the revision, reproduction steps, prediction, observation, and rejection criterion through the [research challenge form](https://github.com/neuron7x/neuron7x/issues/new?template=research-challenge.yml). No issue is created until you submit it.

## cwc

**[CWC](https://github.com/neuron7x/sapolsky-behave-layers)** · revision [f2396198749e](https://github.com/neuron7x/sapolsky-behave-layers/commit/f2396198749ee9cf2d51078cc890e299f51d4bd9)

Adaptive-computation research with explicit identifying assumptions and adversarial causal controls.

| Route | Versioned source | Git blob |
| :--- | :--- | :--- |
| Inspect | [Mechanism](https://github.com/neuron7x/sapolsky-behave-layers/blob/f2396198749ee9cf2d51078cc890e299f51d4bd9/cwc/causal/regime_identifiability.py) | `2531573c80b5` |
| Reproduce | [Reproduction guide](https://github.com/neuron7x/sapolsky-behave-layers/blob/f2396198749ee9cf2d51078cc890e299f51d4bd9/docs/reproducibility/CLEAN_ROOM_REPRODUCTION_PROTOCOL.md) | `eb4bad2af901` |
| Falsify | [Adversarial test](https://github.com/neuron7x/sapolsky-behave-layers/blob/f2396198749ee9cf2d51078cc890e299f51d4bd9/tests/test_csca08_regime_identifiability.py) | `8bc04cf54af5` |
| Boundary | [Claim boundary](https://github.com/neuron7x/sapolsky-behave-layers/blob/f2396198749ee9cf2d51078cc890e299f51d4bd9/README.md) | `746098c702bb` |

**Scope:** The linked regime-identifiability tests distinguish a causal candidate from causal authority, expose assumption violations, and retain untestable exclusion debt.

## bnsyn

**[BN-Syn](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics)** · revision [c1de425ce4ec](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/commit/c1de425ce4ece362e7f2feb2d9f24da5d3231014)

Neural-dynamics simulation with explicit numerical models and property-based probes.

| Route | Versioned source | Git blob |
| :--- | :--- | :--- |
| Inspect | [Mechanism](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/blob/c1de425ce4ece362e7f2feb2d9f24da5d3231014/src/bnsyn/neuron/adex.py) | `a0467c152d98` |
| Reproduce | [Reproduction guide](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/blob/c1de425ce4ece362e7f2feb2d9f24da5d3231014/README.md) | `b4ced723344b` |
| Falsify | [Property-based test](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/blob/c1de425ce4ece362e7f2feb2d9f24da5d3231014/tests/properties/test_adex_properties.py) | `4f5f6e672fe5` |
| Boundary | [Claim boundary](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/blob/c1de425ce4ece362e7f2feb2d9f24da5d3231014/docs/STATUS.md) | `f32cc90a61f1` |

**Scope:** Research / pre-production. Properties of a numerical neuron model do not establish biological fidelity or deployment readiness.

## geosync

**[GeoSync](https://github.com/neuron7x/Kuramoto-synchronization-model)** · revision [2d96756164e1](https://github.com/neuron7x/Kuramoto-synchronization-model/commit/2d96756164e14f9ea24abe9c5ba3a3ff27cc1780)

Quantitative research infrastructure with governed datasets, semantic invariants, and provenance.

| Route | Versioned source | Git blob |
| :--- | :--- | :--- |
| Inspect | [Mechanism](https://github.com/neuron7x/Kuramoto-synchronization-model/blob/2d96756164e14f9ea24abe9c5ba3a3ff27cc1780/core/data/dataset_contracts.py) | `a5125dbc8a42` |
| Reproduce | [Reproduction guide](https://github.com/neuron7x/Kuramoto-synchronization-model/blob/2d96756164e14f9ea24abe9c5ba3a3ff27cc1780/docs/REPRODUCIBILITY.md) | `41002eb8fd2e` |
| Falsify | [Adversarial schema test](https://github.com/neuron7x/Kuramoto-synchronization-model/blob/2d96756164e14f9ea24abe9c5ba3a3ff27cc1780/tests/data/test_dataset_schema_validation.py) | `277c7dd3cb0d` |
| Boundary | [Claim boundary](https://github.com/neuron7x/Kuramoto-synchronization-model/blob/2d96756164e14f9ea24abe9c5ba3a3ff27cc1780/README.md) | `f6f1ba2123cc` |

**Scope:** The linked probe rejects malformed OHLC data. Dataset validation does not establish market predictability or profitability.

## neosynaptex

**[neosynaptex](https://github.com/neuron7x/neosynaptex)** · revision [f70e16a97dcf](https://github.com/neuron7x/neosynaptex/commit/f70e16a97dcfee332eed73ec09328329e7fd55a5)

Cross-substrate scaling diagnostics with explicit estimator definitions and counterexample records.

| Route | Versioned source | Git blob |
| :--- | :--- | :--- |
| Inspect | [Mechanism](https://github.com/neuron7x/neosynaptex/blob/f70e16a97dcfee332eed73ec09328329e7fd55a5/core/gamma.py) | `b1d9eea43237` |
| Reproduce | [Reproduction guide](https://github.com/neuron7x/neosynaptex/blob/f70e16a97dcfee332eed73ec09328329e7fd55a5/README.md) | `f628d90824ff` |
| Falsify | [Recorded counterexample](https://github.com/neuron7x/neosynaptex/blob/f70e16a97dcfee332eed73ec09328329e7fd55a5/results/gamma_specificity/run_v1.json) | `c053667e23ea` |
| Boundary | [Claim boundary](https://github.com/neuron7x/neosynaptex/blob/f70e16a97dcfee332eed73ec09328329e7fd55a5/CANONICAL_POSITION.md) | `bc8b58bef4da` |

**Scope:** An estimated γ ≈ 1 alone is not specific evidence for criticality or metastability. The linked synthetic counterexample record carries its own narrow scope.

## korpus

**[KORPUS](https://github.com/neuron7x/KORPUS)** · revision [cda9db4ae2e4](https://github.com/neuron7x/KORPUS/commit/cda9db4ae2e44ab5c089fe28c06722e1ce49ac93)

Knowledge and inference systems with evidence-bound release admission and explicit authorization.

| Route | Versioned source | Git blob |
| :--- | :--- | :--- |
| Inspect | [Mechanism](https://github.com/neuron7x/KORPUS/blob/cda9db4ae2e44ab5c089fe28c06722e1ce49ac93/apps/api/src/korpus/application/final_release_authorization.py) | `14c8bef91b76` |
| Reproduce | [Reproduction guide](https://github.com/neuron7x/KORPUS/blob/cda9db4ae2e44ab5c089fe28c06722e1ce49ac93/README_FIRST.md) | `eb60946197f1` |
| Falsify | [Release-authorization test](https://github.com/neuron7x/KORPUS/blob/cda9db4ae2e44ab5c089fe28c06722e1ce49ac93/apps/api/tests/test_final_release_authorization.py) | `988f7115774d` |
| Boundary | [Claim boundary](https://github.com/neuron7x/KORPUS/blob/cda9db4ae2e44ab5c089fe28c06722e1ce49ac93/README_FIRST.md) | `eb60946197f1` |

**Scope:** Engineering checks, signed artifacts, and production authorization are distinct. The linked canonical start page records the authorization boundary.

## Maintain the index

The manifest is [`research/atlas.json`](research/atlas.json). Update its references only after inspecting the new source revision; changing a SHA is not scientific validation.

From a checkout of this profile repository, regenerate the atlas and check its consistency:

```bash
python3 tools/render_research_atlas.py
python3 tools/render_research_atlas.py --check
```

To recheck the public Git blob identities, use:

```bash
python3 tools/render_research_atlas.py --check --verify-remote
```

The renderer uses only the Python standard library. Remote verification performs public read requests; it does not execute experiments. There are no scheduled workflows, paid services, or live readiness badges.
