"""Evaluate which sealed ISCAS85 aliases disappear under a frozen wider probe menu."""
import json
import sys
from collections import Counter
from functools import reduce
from itertools import product
from operator import and_, or_, xor
from pathlib import Path

from study import ADAPTIVITY, check, sealed

sys.path.insert(0, str(ADAPTIVITY / "replication"))
from iscas import OPERATIONS, UPSTREAM, load_sources
from generate import digest

PROTOCOL = "8036cc09a090b8fbf30d3e6a051be349ed5c6ca4"
OP_NAMES = {operation: name for name, operation in OPERATIONS.items()}
OPERATORS = {"and": and_, "nand": and_, "or": or_, "nor": or_, "xor": xor}


def packed(circuit, vectors, faults):
    width = len(vectors)
    all_probes = (1 << width) - 1
    force = dict.fromkeys(circuit.nodes, 0)
    set_high = force.copy()
    for lane, (node, bit) in enumerate(faults, 1):
        (set_high if bit else force)[node] |= all_probes << (lane * width)
    lane_count = len(faults) + 1
    all_bits = (1 << (width * lane_count)) - 1
    repeat = all_bits // all_probes
    cells = {
        name: repeat * sum(vector[index] << i for i, vector in enumerate(vectors))
        for index, name in enumerate(circuit.inputs)
    }
    for node, operation, fanins in circuit.gates:
        op = OP_NAMES[operation]
        if op in ("not", "buf"):
            value = cells[fanins[0]]
        else:
            value = reduce(OPERATORS[op], (cells[signal] for signal in fanins))
        if op in ("not", "nand", "nor"):
            value ^= all_bits
        cells[node] = (value | set_high[node]) & ~force[node]

    outputs = [cells[signal] for signal in circuit.outputs]
    return [
        ["".join(str((value >> (truth * width + i)) & 1) for value in outputs)
         for i in range(width)]
        for truth in range(lane_count)
    ]


def requested_inputs(path, index, inputs):
    if path.endswith("/c17.v"):
        check(len(inputs) == 5, "unexpected exhaustive input space for c17")
        return list(product((0, 1), repeat=5))
    return [tuple(digest(path, index, "input", probe, signal, namespace="A04")[0] & 1
                  for signal in inputs)
            for probe in range(64)]


def unique(matrix, limit):
    counts = Counter(tuple(row[:limit]) for row in matrix)
    return sum(size == 1 for size in counts.values())


def summarize(record, baseline):
    counts = []
    check(record["schema"] == "a04.wider-observations.v1" and record["protocol"] == PROTOCOL
          and record["upstream"] == UPSTREAM, "wider observation provenance mismatch")
    for fresh, old in zip(record["sources"], baseline["sources"], strict=True):
        path = fresh["path"]
        check(path == old["path"] and fresh["sha256"] == old["sha256"] and
              len(fresh["cases"]) == len(old["cases"]) == 16, "wider panel inventory mismatch")
        stops = [0, 4, 8, 16, 32] if path.endswith("/c17.v") else [0, 4, 8, 16, 32, 64]
        totals = dict.fromkeys(stops, 0)
        for index, (case, prior) in enumerate(zip(fresh["cases"], old["cases"], strict=True)):
            matrix = case["matrix"]
            extra = ["".join(map(str, row))
                     for row in requested_inputs(path, index, fresh["inputs"])]
            check(case["index"] == index and case["extra_vectors"] == extra, "wider probe IDs changed")
            check(len(matrix) == 8 and all(len(row) == 7 + stops[-1] for row in matrix)
                  and [row[:7] for row in matrix] == prior["matrix"], "initial responses disagree")
            per_probe = [unique(matrix, end) for end in range(7, 8 + stops[-1])]
            check(per_probe == sorted(per_probe), "unique coverage decreased")
            for count in stops:
                totals[count] += 8 - per_probe[count]
        counts.append({"path": path, "aliases_after_extra_probes": totals,
                       "recovered": totals[0] - totals[stops[-1]],
                       "remaining": totals[stops[-1]], "baseline": totals[0]})
    before = sum(row["baseline"] for row in counts)
    recovered = sum(row["recovered"] for row in counts)
    return {"baseline_alias_rows": before, "resolved_rows": recovered, "remaining_rows": before-recovered,
            "majority_resolved": 2 * recovered > before, "circuits": counts}


def run(source):
    baseline, anchor = sealed(ADAPTIVITY / "replication" / "evidence", "inputs.json")
    entries = []
    checked = 0
    for (path, oid, sha, circuit), old in zip(load_sources(source), baseline["sources"], strict=True):
        check((path, oid, sha) == (old["path"], old["oid"], old["sha256"]), "source trace mismatch")
        cases = []
        for index, prior in enumerate(old["cases"]):
            faults = [tuple(fault) for fault in prior["faults"][1:]]
            old_vectors = [tuple(map(int, bits)) for bits in prior["probes"]]
            added = requested_inputs(path, index, circuit.inputs)
            matrix = packed(circuit, [*old_vectors, *added], faults)
            if index == 0:
                scalar = list(zip(*(circuit.simulate(v, faults) for v in added), strict=True))
                check([tuple(row[7:]) for row in matrix] == scalar, "scalar simulator disagrees")
                checked += len(added) * len(matrix)
            cases.append({"index": index, "extra_vectors": ["".join(map(str, v)) for v in added],
                          "matrix": matrix})
        entries.append({"path": path, "sha256": sha, "inputs": circuit.inputs, "cases": cases})
    result = {"schema": "a04.wider-observations.v1", "upstream": UPSTREAM, "protocol": PROTOCOL,
              "input_sha256": anchor, "independent_scalar_checks": checked, "sources": entries}
    result["summary"] = summarize(result, baseline)
    return result


if __name__ == "__main__":
    check(len(sys.argv) == 2, "usage: python3 wider.py PINNED_ISCAS_CHECKOUT")
    print(json.dumps(run(Path(sys.argv[1])), separators=(",", ":")))
