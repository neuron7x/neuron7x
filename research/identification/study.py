"""Recalculate all identification bounds against sealed A01 and A02 cases."""
import gzip
import hashlib
import json
import sys
from collections import Counter
from itertools import combinations, product
from pathlib import Path

from lattice import FIELDS, GAPS, gaps, measure
from subset_oracle import oracle

STUDY = Path(__file__).resolve().parent
ADAPTIVITY = STUDY.parent / "adaptivity"
PROTOCOL = "343cd2d241bfead61fd464c0e0323e3162804002"


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def sealed(evidence, name):
    index = dict(tuple(reversed(line.split("  ")))
                 for line in (evidence / "SHA256SUMS").read_text().splitlines())
    contents = gzip.decompress((evidence / (name + ".gz")).read_bytes())
    check(hashlib.sha256(contents).hexdigest() == index[name], f"invalid sealed hash for {name}")
    return json.loads(contents), index[name]


def exact(matrix):
    likely = measure(matrix)
    separate = oracle(matrix)
    check(likely == separate, "independent subset checker disagrees")
    return likely


def archive(evidence, revision):
    panel, inputs_sha = sealed(evidence, "inputs.json")
    traces, traces_sha = sealed(evidence, "traces.json")
    check(panel["schema"] == f"{revision}.inputs.v1" and traces["schema"] == f"{revision}.traces.v1",
          "panel schema mismatch")
    trace_key, input_hash_key = (("result", "input_sha256") if revision == "a01" else
                                 ("sources", "inputs_sha256"))
    families = 20 if revision == "a01" else 11
    check(len(panel["sources"]) == len(traces[trace_key]) == families and
          traces[input_hash_key] == inputs_sha, "panel size or trace anchor mismatch")

    totals = Counter()
    per_source = []
    for source, traced in zip(panel["sources"], traces[trace_key], strict=True):
        check(source["path"] == traced["path"] and len(source["cases"]) == len(traced["cases"]) == 16,
              "invalid family inventory")
        cases = []
        for index, (case, previous) in enumerate(zip(source["cases"], traced["cases"], strict=True)):
            matrix = case["matrix"]
            check(case["index"] == index and len(matrix) == 8 and all(len(row) == 7 for row in matrix),
                  "invalid matrix shape")
            available = exact([row[:6] for row in matrix])
            observable = exact(matrix)
            check((available["A"], observable["A"], available["F"]) ==
                  (previous["bound"], previous["fullBound"],
                   sum(trial["selected"] for trial in previous["policies"]["fixed"])),
                  "sealed adaptive/fixed orbit disagreement")
            parts = gaps(len(matrix), observable, available)
            totals.update(parts)
            cases.append({"case": index, "six": available, "seven": observable, "gaps": parts})
        per_source.append({"path": source["path"], "cases": cases})
    return {"inputs_sha256": inputs_sha, "traces_sha256": traces_sha,
            "gaps": dict(totals), "catalog_rows": families * 16 * 8, "sources": per_source}


def exhaustive_binary():
    rows = tuple(product("01", repeat=4))
    totals = Counter()
    records = []
    for ids in combinations(range(16), 6):
        matrix = [rows[index] for index in ids]
        counts = exact(matrix)
        parts = gaps(6, counts, counts)
        totals.update(parts)
        records.append([list(ids), *(counts[key] for key in FIELDS)])
    check(len(records) == 8008 and totals["adaptivity"] == 2688, "binary calibration changed")
    return {"row_encoding": "lexical binary signatures 0000..1111",
            "record_fields": ["row_ids", *FIELDS], "gaps": dict(totals), "records": records}


def run():
    return {"schema": "a03.identification-limits.v1", "protocol": PROTOCOL,
            "a01": archive(ADAPTIVITY / "evidence", "a01"),
            "a02": archive(ADAPTIVITY / "replication" / "evidence", "a02"),
            "binary": exhaustive_binary()}


if __name__ == "__main__":
    check(len(sys.argv) == 1, "usage: python3 study.py")
    print(json.dumps(run(), separators=(",", ":")))
