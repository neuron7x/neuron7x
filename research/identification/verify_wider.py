"""Replay every wider outcome with the scalar simulator from A02."""
import sys
from pathlib import Path

from wider import ADAPTIVITY, check, load_sources, sealed, summarize

STUDY = Path(__file__).resolve().parent


def verify(source):
    wider, wider_sha = sealed(STUDY / "evidence", "wider.json")
    baseline, baseline_sha = sealed(ADAPTIVITY / "replication" / "evidence", "inputs.json")
    check(wider["input_sha256"] == baseline_sha, "baseline hash mismatch")
    checked = 0
    for (path, oid, fingerprint, circuit), before, after in zip(
        load_sources(source), baseline["sources"], wider["sources"], strict=True
    ):
        check((path, oid, fingerprint) == (before["path"], before["oid"], before["sha256"]) and
              tuple(after["inputs"]) == circuit.inputs, "source digest or input order mismatch")
        for prior, actual in zip(before["cases"], after["cases"], strict=True):
            faults = [tuple(fault) for fault in prior["faults"][1:]]
            vectors = (*prior["probes"], *actual["extra_vectors"])
            for index, vector in enumerate(vectors):
                expected = circuit.simulate(tuple(map(int, vector)), faults)
                observed = tuple(row[index] for row in actual["matrix"])
                check(expected == observed, f"scalar mismatch {path} case {prior['index']} probe {index}")
                checked += len(expected)
    result = summarize(wider, baseline)
    print(f"WIDER_SHA256 {wider_sha}")
    print(f"SCALAR_MODEL_PROBE_AGREEMENTS {checked}")
    print(f"RESOLVED {result['resolved_rows']} / {result['baseline_alias_rows']}")


if __name__ == "__main__":
    check(len(sys.argv) == 2, "usage: python3 verify_wider.py PINNED_ISCAS_CHECKOUT")
    verify(Path(sys.argv[1]))
