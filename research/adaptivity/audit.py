"""Verify policy choices from observed histories and report the EC² contrast."""
import hashlib
import itertools
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

from decide import DELTA, POLICIES, replay, require, summarize


def signatures(rows, probes):
    return Counter(tuple(row[probe] for probe in probes) for row in rows)


def unique(rows, probes):
    return sum(value == 1 for value in signatures(rows, probes).values())


def roots(matrix, probes):
    for first in probes:
        branches = [[row for row in matrix if row[first] == outcome]
                    for outcome in dict.fromkeys(row[first] for row in matrix)]
        tails = [1 if len(group) == 1 else max(
                 (unique(group, (p,)) for p in probes if p != first), default=0)
                 for group in branches]
        uses = len(matrix) + sum(len(group) for group, recovered in zip(branches, tails, strict=True)
                                 if len(group) > 1 and recovered)
        yield (sum(tails), -uses, first)


def fixed_plan(matrix, probes):
    plans = [(0, 0, ())]
    for first in probes:
        one = unique(matrix, (first,))
        plans.append((one, -len(matrix), (first,)))
        for second in probes:
            if second != first:
                plans.append((unique(matrix, (first, second)), one - 2 * len(matrix), (first, second)))
    return list(min(plans, key=lambda plan: (-plan[0], -plan[1], plan[2]))[2])


def action(matrix, probes, name):
    scores = []
    for p in probes:
        outcomes = [row[p] for row in matrix]
        if len(set(outcomes)) < 2:
            continue
        if name == "pairs":
            score = sum(a != b for a, b in itertools.combinations(outcomes, 2))
        elif name == "singleton":
            score = sum(outcomes.count(value) == 1 for value in outcomes)
        else:
            edges = list(itertools.combinations(outcomes, 2))
            score = sum(left != value or right != value for value in outcomes for left, right in edges)
        scores.append((score, -p))
    return -max(scores)[1] if scores else None


def audit_case(matrix, evaluated, ec2_trials):
    probes = tuple(range(6))
    root_scores = list(roots(matrix, probes))
    best, _, root = max(root_scores, key=lambda key: (key[0], key[1], -key[2]))
    require(evaluated["bound"] == best and
            evaluated["fullBound"] == max(score for score, _, _ in roots(matrix, range(7))),
            "oracle is not the enumerated bound")
    plans = {**evaluated["policies"], "ec2": ec2_trials}
    fixed = fixed_plan(matrix, probes)
    ec2_selected = replay(matrix, "ec2", ec2_trials)
    for name in (*POLICIES, "ec2"):
        for row, trial in zip(matrix, plans[name], strict=True):
            if name == "fixed":
                require(trial["fixed"] == fixed, "fixed plan is not optimal")
                continue
            first = (root if best else None) if name == "exact" else action(matrix, probes, name)
            expected = [] if first is None else [first]
            if first is not None:
                viable = [other for other in matrix if other[first] == row[first]]
                if len(viable) > 1:
                    available = [probe for probe in probes if probe != first]
                    if name == "exact":
                        count, neg_index = max((unique(viable, (probe,)), -probe)
                                               for probe in available)
                        second = -neg_index if count else None
                    else:
                        second = action(viable, available, name)
                    if second is not None:
                        expected.append(second)
            require(trial["trace"] == expected, f"{name} action disagrees with observed-history oracle")
    return ec2_selected


def audit(inputs_bytes, traces_bytes, ec2_bytes):
    decision = summarize(inputs_bytes, traces_bytes)
    sources = json.loads(inputs_bytes)["sources"]
    records = json.loads(traces_bytes)["result"]
    supplement = json.loads(ec2_bytes)
    require(supplement["schema"] == "a01.ec2.v1" and
            supplement["input_sha256"] == decision["input_sha256"], "EC2 panel hash mismatch")
    families = []
    for source, record, other, primary in zip(sources, records, supplement["result"],
                                               decision["families"], strict=True):
        require(source["path"] == other["path"], "EC2 family mismatch")
        selected = sum(audit_case(case["matrix"], evaluated, comparator)
                       for case, evaluated, comparator in
                       zip(source["cases"], record["cases"], other["cases"], strict=True))
        families.append({"path": source["path"], "ec2": selected,
                         "delta": str(Fraction(primary["exact"] - selected, 128))})

    effects = sorted(Fraction(family["delta"]) for family in families)
    low, high = effects[4], effects[15]
    return {"schema": "a01.audit.v1", "primary_decision": decision["decision"],
            "primary_trace_sha256": decision["trace_sha256"],
            "ec2_trace_sha256": hashlib.sha256(ec2_bytes).hexdigest(),
            "ec2_selections": sum(family["ec2"] for family in families),
            "mean": str(sum(effects)/20), "median_interval": [str(low), str(high)],
            "ec2_decision": "REFUTED_PRACTICAL_ADVANTAGE_A01_L" if high <= DELTA else
            "PRELIMINARY_SUPPORT_A01_L" if low > DELTA else "INCONCLUSIVE_A01_L",
            "families": families}


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: python3 audit.py INPUT.json TRACES.json EC2.json")
    print(json.dumps(audit(*(Path(arg).read_bytes() for arg in sys.argv[1:])), indent=2))
