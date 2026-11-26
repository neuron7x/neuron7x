"""Run and independently score the frozen ISCAS85 transfer panel."""
import hashlib
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from iscas import CIRCUITS, PROTOCOL, UPSTREAM, load_sources, require

from audit import audit_case
from decide import DELTA, POLICIES, replay
from generate import generate_case

STUDY = Path(__file__).resolve().parent
COMPARATORS = ("fixed", "pairs", "singleton", "ec2")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def generate(source):
    return {
        "schema": "a02.inputs.v1", "protocol": PROTOCOL, "upstream": UPSTREAM,
        "sources": [
            {"path": path, "oid": oid, "sha256": digest,
             "cases": [generate_case(path, i, circuit, "A02") for i in range(16)]}
            for path, oid, digest, circuit in load_sources(source)
        ],
    }


def decision(contrasts):
    bounds = [tuple(map(Fraction, result["interval"])) for result in contrasts.values()]
    if any(high <= DELTA for _, high in bounds):
        return "REFUTED_PRACTICAL_ADVANTAGE_A02"
    if all(low > DELTA for low, _ in bounds):
        return "SUPPORT_A02"
    return "INCONCLUSIVE_A02"


def summarize(inputs, traces):
    panel, outputs = json.loads(inputs), json.loads(traces)
    require(panel["schema"] == "a02.inputs.v1" and panel["protocol"] == PROTOCOL and
            panel["upstream"] == UPSTREAM, "panel revision mismatch")
    require(outputs["schema"] == "a02.traces.v1" and outputs["inputs_sha256"] == sha(inputs),
            "trace anchor mismatch")
    circuits = {}
    maxima = dict.fromkeys((*POLICIES, "ec2"), 0)
    for circuit, source, traced in zip(CIRCUITS, panel["sources"], outputs["sources"], strict=True):
        path = f"logikbench/benchmarks/iscas85/{circuit}/rtl/{circuit}.v"
        require(source["path"] == traced["path"] == path and
                len(source["cases"]) == len(traced["cases"]) == 16, "invalid family inventory")
        require(len(source["oid"]) == 40 and len(source["sha256"]) == 64 and
                all(c in "0123456789abcdef" for c in source["oid"] + source["sha256"]),
                "invalid source digests")
        counts = dict.fromkeys((*POLICIES, "ec2", "bound", "fullBound"), 0)
        for i, (case, result) in enumerate(zip(source["cases"], traced["cases"], strict=True)):
            require(case["index"] == i, "case index mismatch")
            matrix = case["matrix"]
            counts["ec2"] += audit_case(matrix, result, result["ec2"])
            for name in POLICIES:
                trials = result["policies"][name]
                counts[name] += replay(matrix, name, trials)
                maxima[name] = max(maxima[name], *(trial["accesses"] for trial in trials))
            require(sum(trial["selected"] for trial in result["policies"]["exact"]) ==
                    result["bound"], "limited optimum mismatch")
            maxima["ec2"] = max(maxima["ec2"], *(trial["accesses"] for trial in result["ec2"]))
            for bound in ("bound", "fullBound"):
                counts[bound] += result[bound]
        circuits[circuit] = counts

    families = [(name,) for name in CIRCUITS if name not in ("c499", "c1355")]
    families.append(("c499", "c1355"))
    contrasts = {}
    for name in COMPARATORS:
        effects = {
            "+".join(group): Fraction(sum(circuits[member]["exact"] - circuits[member][name]
                                         for member in group), 128 * len(group))
            for group in families
        }
        contrasts[name] = {"family_effects": {key: str(value) for key, value in effects.items()},
                           "mean": str(sum(effects.values()) / len(families)),
                           "interval": [str(min(effects.values())), str(max(effects.values()))]}

    return {"schema": "a02.result.v1", "inputs_sha256": sha(inputs), "traces_sha256": sha(traces),
            "decision": decision(contrasts), "delta": str(DELTA), "trials_per_policy": len(CIRCUITS)*128,
            "max_accesses_per_trial": maxima,
            "circuits": circuits, "contrasts": contrasts}


def compare(path):
    return subprocess.run(["node", str(STUDY / "compare.mjs"), str(path)], check=True,
                          capture_output=True, timeout=30).stdout


def main(source, target):
    target.mkdir()
    inputs = (json.dumps(generate(source), separators=(",", ":")) + "\n").encode()
    (target / "inputs.json").write_bytes(inputs)
    traces = compare(target / "inputs.json")
    (target / "traces.json").write_bytes(traces)
    output = summarize(inputs, traces)
    (target / "result.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(output["decision"])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python3 run.py PINNED_ISCAS_CHECKOUT NEW_RESULT_DIRECTORY")
    main(*map(Path, sys.argv[1:]))
