# ⊛ Epistemic Signal

A content-sensitive, source-pinned visual footer for [NEURON7X](README.md). No GitHub popularity scores, fabricated experimental results, CI readiness claims, or paid services.

## Interpretation contract

Each node is one project from [research/atlas.json](research/atlas.json). Its four small ports mean there are commit-pinned **references** for `inspect`, `reproduce`, `falsify`, and `boundary`. The red port denotes the **falsification route type**; it is **not** a passing test. A dashed bridge denotes two roles sharing one exact Git blob — in the 2026-10-12 snapshot, KORPUS uses the same `README_FIRST.md` blob for reproduction and boundary.

The curved lines and the eight-digit FNV-1a visual key are deterministic **decoration tied to source identity**, not measured neural oscillations, causal strength, scientific confidence, or a cryptographic signature. Consult the SHA-256 atlas fingerprint and pinned source references in [RESEARCH_ATLAS.md](RESEARCH_ATLAS.md) for the underlying provenance. A fingerprint is not proof of scientific correctness.

The `verified_date` is the date of the source audit recorded in the manifest. It is **not** a claim of live verification. The profile's existing atlas states that project experiments **were not executed** for that audit; this visualization makes the execution boundary explicit.

## Verification and maintenance

```bash
node tools/render_epistemic_signal.mjs
node tools/render_epistemic_signal.mjs --check
node --test tests/epistemic_signal.test.mjs
python3 tools/render_research_atlas.py --check
```

Standard Node.js 20+; no external npm dependencies or network operations. The generator fails closed on missing or extra evidence roles, non-SHA references, unsafe paths, duplicate slugs, and verification-scope mismatches. The four transparent SVGs cover desktop/mobile and dark/light theme variants. Their structured text and XML are checked by GitHub Actions.

**Protected:** the original `assets/neuro-code.webp` animation and all existing Research Atlas outputs remain unchanged. The previous `assets/research-signature-*.svg` files remain in the repository for straightforward rollback.

**Scientific boundary:** commit-pinned source metadata alone does not establish experimental reproducibility, independent replication, biological fidelity, safety, or deployment readiness.
