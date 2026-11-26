"""Independently replay traces and apply the frozen A01 decision rule."""
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

BASELINES = ("fixed", "pairs", "singleton")
POLICIES = ("exact", *BASELINES)
DELTA = Fraction(1, 20)


def require(condition, error):
    if not condition:
        raise ValueError(error)


def replay(matrix, name, trials):
    require(len(trials) == 8, "incomplete truth sweep")
    plan = trials[0]["fixed"]
    require((isinstance(plan, list) and len(plan) <= 2 and len(set(plan)) == len(plan) and
             all(type(probe) is int and 0 <= probe < 6 for probe in plan)) if name == "fixed"
            else plan is None, "invalid precommitted pair")
    for truth, trial in enumerate(trials):
        trace = trial["trace"]
        require(isinstance(trace, list) and len(trace) <= 2 and len(set(trace)) == len(trace)
                and all(type(probe) is int and 0 <= probe < 6 for probe in trace), "invalid trace")
        require(type(trial["accesses"]) is int and 48 <= trial["accesses"] <= 384
                and type(trial["reads"]) is int and trial["reads"] == 48, "invalid resource claim")
        require(trial["fixed"] == plan and (plan is None or trace == plan[:len(trace)]),
                "fixed plan changed after outcome")
        matching = [row for row in matrix if all(row[p] == matrix[truth][p] for p in trace)]
        require(trial["selected"] is bool(trace and len(matching) == 1), "invalid claim of identification")
        if len(trace) == 2:
            require(sum(row[trace[0]] == matrix[truth][trace[0]] for row in matrix) > 1,
                    "continued after identification")
        if plan is not None and len(trace) < len(plan):
            require(trial["selected"], "fixed plan abandoned")
    return sum(trial["selected"] for trial in trials)


def summarize(inputs_bytes, traces_bytes):
    inputs = json.loads(inputs_bytes)
    traces = json.loads(traces_bytes)
    require(inputs["schema"] == "a01.inputs.v1" and traces["schema"] == "a01.traces.v1",
            "unknown artifact schema")
    require(traces["input_sha256"] == hashlib.sha256(inputs_bytes).hexdigest(), "input hash mismatch")
    require(len(inputs["sources"]) == len(traces["result"]) == 20, "incomplete panel")
    require(len({source["path"] for source in inputs["sources"]}) == 20, "duplicate family")
    families = []
    maxima = dict.fromkeys(POLICIES, 0)
    for source, record in zip(inputs["sources"], traces["result"], strict=True):
        require(source["path"] == record["path"] and
                len(source["cases"]) == len(record["cases"]) == 16, "incomplete family")
        totals = dict.fromkeys((*POLICIES, "bound", "fullBound"), 0)
        for i, (case, evaluated) in enumerate(zip(source["cases"], record["cases"], strict=True)):
            matrix = case["matrix"]
            require(case["index"] == i and len(matrix) == 8 and all(len(row) == 7 for row in matrix),
                    "invalid truth matrix")
            for name in POLICIES:
                trials = evaluated["policies"][name]
                totals[name] += replay(matrix, name, trials)
                maxima[name] = max(maxima[name], *(trial["accesses"] for trial in trials))
            bound, full_bound = evaluated["bound"], evaluated["fullBound"]
            require(bound == sum(row["selected"] for row in evaluated["policies"]["exact"])
                    and bound <= full_bound <= 8, "invalid oracle bound")
            totals["bound"] += bound
            totals["fullBound"] += full_bound
        families.append({"path": source["path"], **totals})

    contrasts = {}
    for name in BASELINES:
        effects = sorted(Fraction(row["exact"] - row[name], 128) for row in families)
        contrasts[name] = {
            "mean": str(sum(effects) / 20),
            "median_interval": [str(effects[4]), str(effects[15])],
        }
    intervals = [tuple(map(Fraction, contrast["median_interval"])) for contrast in contrasts.values()]
    if any(high <= DELTA for _, high in intervals):
        decision = "REFUTED_PRACTICAL_ADVANTAGE_A01"
    elif all(low > DELTA for low, _ in intervals):
        decision = "PRELIMINARY_SUPPORT_A01"
    else:
        decision = "INCONCLUSIVE_A01"
    return {
        "schema": "a01.decision.v1",
        "input_sha256": hashlib.sha256(inputs_bytes).hexdigest(),
        "trace_sha256": hashlib.sha256(traces_bytes).hexdigest(),
        "trials_per_policy": 2560,
        "selections": {name: sum(row[name] for row in families)
                       for name in (*POLICIES, "bound", "fullBound")},
        "max_accesses_per_trial": maxima,
        "delta": str(DELTA),
        "contrasts": contrasts,
        "decision": decision,
        "families": families,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python3 decide.py INPUT.json TRACES.json")
    print(json.dumps(summarize(*(Path(arg).read_bytes() for arg in sys.argv[1:])), indent=2))
