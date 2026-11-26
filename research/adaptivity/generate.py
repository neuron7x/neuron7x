"""Generate the fixed A01 panel from a pinned upstream worktree."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from epfl import load_sources

UPSTREAM = "82d8cc6910419298e713a46644ed59fd3df53038"
PROTOCOL = "1d24e98aec1df58814544dcaadd2c672df853612"


def digest(*parts):
    return hashlib.sha256("|".join(map(str, ("A01", *parts))).encode("utf-8")).digest()


def generate_case(path, index, circuit):
    faults = sorted(
        ((node, bit) for node in circuit.nodes for bit in (0, 1)),
        key=lambda fault: (digest(path, index, "fault", *fault), fault),
    )[:7]
    if len(faults) != 7:
        raise ValueError(f"insufficient fault sites in {path}")
    probes = [
        tuple(digest(path, index, "input", probe, signal)[0] & 1 for signal in circuit.inputs)
        for probe in range(7)
    ]
    matrix = tuple(zip(*(circuit.simulate(bits, faults) for bits in probes), strict=True))
    return {
        "index": index,
        "faults": [None, *faults],
        "probes": ["".join(map(str, bits)) for bits in probes],
        "matrix": matrix,
    }


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True)


def generate(source):
    if git(source, "rev-parse", "HEAD").strip() != UPSTREAM:
        raise ValueError("upstream revision mismatch")
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("upstream worktree differs from the pinned revision")
    sources = [
        {"path": name, "sha256": sha, "cases": [generate_case(name, i, circuit) for i in range(16)]}
        for name, sha, circuit in load_sources(source)
    ]
    if len(sources) != 20 or len({source["path"] for source in sources}) != 20:
        raise ValueError("incomplete upstream panel")
    return {"schema": "a01.inputs.v1", "protocol": PROTOCOL, "upstream": UPSTREAM, "sources": sources}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 generate.py EPFL_CHECKOUT")
    print(json.dumps(generate(Path(sys.argv[1])), separators=(",", ":")))
