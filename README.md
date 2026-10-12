<p align="center">
  <img src="./assets/neuro-code.webp" width="100%" alt="Neural code animation" />
</p>

<!-- The original brain animation is intentional. Preserve its file and reference. -->

<h1 align="center">Yaroslav Vasylenko</h1>

<p align="center">
  <strong>Independent NeuroAI Researcher · AI Systems Architect</strong><br>
  Computational neuroscience · Cognitive architectures · Technical AI safety
</p>

<p align="center">
  <a href="#selected-research">Research</a> ·
  <a href="#engineering-practice">Engineering</a> ·
  <a href="#collaborate">Collaborate</a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/research-signature-dark.svg">
    <img src="./assets/research-signature-light.svg" width="100%" alt="Decorative phase signature: dynamics, control, and evidence">
  </picture>
</p>

I translate neural and cognitive mechanisms into computational models,
constrained controllers, and reproducible evaluation systems. My research
asks which adaptive mechanisms change behavior under controlled interventions
and explicit compute budgets—and where those mechanisms fail.

At the AI systems layer, I build explicit control around probabilistic
generation: typed contracts, bounded authority, fail-closed decisions,
and replayable evidence.

**Ukraine · Independent research · Remote collaboration**

## Selected research

| Project | Research / engineering focus | Inspect |
| :--- | :--- | :--- |
| **[Cognitive Wiring Core](https://github.com/neuron7x/sapolsky-behave-layers)** | Causal evaluation of adaptive computation: budget-matched experiments, intervention controls, and falsification harnesses. | [System map](https://github.com/neuron7x/sapolsky-behave-layers/blob/main/SYSTEM.md) · [Interventions](https://github.com/neuron7x/sapolsky-behave-layers/blob/main/cwc/causal/interventions.py) |
| **[BN-Syn](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics)** | Neural-dynamics simulation with AdEx neurons, STDP plasticity, criticality control, and reproducibility checks. | [Neuron model](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/blob/main/src/bnsyn/neuron/adex.py) · [Status](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/blob/main/docs/STATUS.md) |
| **[GeoSync](https://github.com/neuron7x/Kuramoto-synchronization-model)** | Quantitative research infrastructure for falsifiable market-structure hypotheses, with explicit data contracts and provenance. | [Dataset contracts](https://github.com/neuron7x/Kuramoto-synchronization-model/blob/main/core/data/dataset_contracts.py) |
| **[neosynaptex](https://github.com/neuron7x/neosynaptex)** | Cross-substrate scaling diagnostics: null models, counterexample search, and explicit limits on what an estimator can establish. | [Canonical position](https://github.com/neuron7x/neosynaptex/blob/main/CANONICAL_POSITION.md) · [Research direction](https://github.com/neuron7x/neosynaptex/blob/main/docs/RESEARCH_DIRECTION.md) |
| **[KORPUS](https://github.com/neuron7x/KORPUS)** | Evidence-bound knowledge and inference systems: authorization, abstention, auditability, and explicit release admission. | [Start here](https://github.com/neuron7x/KORPUS/blob/main/README_FIRST.md) · [Release authorization](https://github.com/neuron7x/KORPUS/blob/main/apps/api/src/korpus/application/final_release_authorization.py) |

CWC builds on [Andrej Karpathy's nanochat](https://github.com/karpathy/nanochat).
The original contribution is the CWC research, instrumentation, and evaluation
layer; upstream attribution is preserved in the repository.

## Engineering practice

I work from **mechanism → invariant → falsifier → evidence**.

- **Causal evaluation:** controlled interventions, ablations, matched baselines,
  and explicit limits on inference.
- **Neural and cognitive systems:** dynamical models, constrained autonomy,
  and inspectable state transitions.
- **Agent reliability:** tool boundaries, structured outputs, policy gates,
  and separation of generation from acceptance.
- **Software assurance:** property-based and mutation testing, deterministic
  replay, schema validation, provenance, and CI gates.

**Core tools:** Python · NumPy / SciPy · FastAPI / Pydantic ·
pytest / Hypothesis · Docker · Linux · GitHub Actions / GitLab CI

<details>
<summary><strong>Evidence and scope</strong></summary>

Experimental findings are conditional on their documented substrates,
datasets, interventions, and compute budgets. Negative results remain part
of the research record.

CWC's budgeted-computation programme and BN-Syn's neural simulations remain
research work. KORPUS distinguishes engineering checks from production
authorization. The neosynaptex canon records why an estimated γ ≈ 1 alone
cannot establish criticality or metastability.

Current status and supporting evidence belong to the linked project sources.
Independent replication and deployment require their own evidence.

</details>

## Collaborate

Open to research collaboration and focused engineering engagements in
NeuroAI, cognitive architectures, technical AI safety evaluation, and
agent reliability.

[Email](mailto:neuron7x@gmail.com) ·
[Telegram](https://t.me/neuron7x) ·
[NEURON7X services](https://neuron7x-site-140887.gitlab.io/)

<p align="center"><sub>⊛ Vita est certamine.</sub></p>
