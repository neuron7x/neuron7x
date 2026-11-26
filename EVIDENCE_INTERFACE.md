# ⊛ Epistemic Signal

A content-sensitive, source-pinned visual footer for [NEURON7X](README.md). No GitHub popularity scores, fabricated experimental results, CI readiness claims, or paid services.

## Interpretation contract

Each node is one project from [research/atlas.json](research/atlas.json). Its four small ports mean there are commit-pinned **references** for `inspect`, `reproduce`, `falsify`, and `boundary`. The red port denotes the **falsification route type**; it is **not** a passing test. A dashed bridge denotes two roles sharing one exact Git blob — in the 2026-10-12 snapshot, KORPUS uses the same `README_FIRST.md` blob for reproduction and boundary.

The curved lines and the eight-digit FNV-1a visual key are deterministic **decoration tied to source identity**, not measured neural oscillations, causal strength, scientific confidence, or a cryptographic signature. Consult the SHA-256 atlas fingerprint and pinned source references in [RESEARCH_ATLAS.md](RESEARCH_ATLAS.md) for the underlying provenance. A fingerprint is not proof of scientific correctness.

The `verified_date` is the date of the source audit recorded in the manifest. It is **not** a claim of live verification. The profile's existing atlas states that project experiments **were not executed** for that audit; this visualization makes the execution boundary explicit.

## Verification and maintenance

Run `python3 tools/verify_release.py <commit>` to check the exact local Git revision in a clean archive. Before running tests, it checks every archived path, executable mode and Git blob hash against the selected tree, with Git replacement objects disabled. Run the verifier from the selected revision so the executing verifier matches the committed file. It then runs both test suites, checks inference traces and generated artifacts, and requires known failures after controlled changes. The command prints the commit, Git tree, number of verified blobs, verifier SHA-256 and checks actually executed. Use `--report <file.json>` for a deterministic JSON record of the checks reached, their expected and observed exit codes and the failing stage if applicable. Its controlled changes include detached receipt anchors, inflated forecast counts, a symlink admitted as a regular tree leaf and coherent plans that lose coverage, waste actions or choose the wrong lexical tie. Remote Git blob verification is a separate read-only check via `python3 tools/render_research_atlas.py --check --verify-remote`. It resolves the pinned root from GitHub, recomputes each traversed tree hash, and checks the path and regular file mode before checking the returned file type, decoded size and Git blob hash.


```bash
node tools/render_epistemic_signal.mjs
node tools/render_epistemic_signal.mjs --check
node --test tests/epistemic_signal.test.mjs
python3 tools/render_research_atlas.py --check
```

Standard Node.js 20+; no external npm dependencies or network operations. The generator fails closed on missing or extra evidence roles, non-SHA references, unsafe paths, duplicate slugs, and verification-scope mismatches. The four transparent SVGs cover desktop/mobile and dark/light theme variants. The local release gate runs offline with no project dependencies. GitHub Actions runs it in separate jobs for the PR head and merge preview, and on the actual commit pushed to `main`. Each job exposes its report as a run artifact. The workflow has read-only repository permissions. The gate checks repository behavior on an exact revision. Scientific conclusions and remote-source checks retain their separate evidence requirements.

For full remote source verification, run the following from the selected committed revision:

```sh
python3 -B -m tools.verify_sources HEAD --report source-verification.json
```

The source command uses an existing authenticated `neuron7x` login, restricted to its published repositories. It reads raw commit objects in temporary Git repositories, checks GitHub's reported roots against them, then verifies each pinned tree and blob. The resulting report includes the revision, atlas fingerprint, validated commits and source-request count.

**Protected:** the original `assets/neuro-code.webp` animation and all existing Research Atlas outputs remain unchanged. The previous `assets/research-signature-*.svg` files remain in the repository for straightforward rollback.

**Scientific boundary:** commit-pinned source metadata alone does not establish experimental reproducibility, independent replication, biological fidelity, safety, or deployment readiness.
