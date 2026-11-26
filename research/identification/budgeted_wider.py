"""Exact wide-menu depth-two coverage and the range on newly unique rows."""
import json
from itertools import combinations

from lattice import partition
from study import STUDY, check, sealed
from subset_oracle import _can_share_tree

PROTOCOL = "b23f65fc01fa6df17d188513a04bf50fd8c31bb2"


def signature_singletons(matrix, width):
    return {next(iter(group)) for group in partition(tuple(row[:width]) for row in matrix)
            if len(group) == 1}


def projected(matrix, recovered):
    columns = tuple(zip(*matrix, strict=True))
    probes = range(len(columns))
    isolated = {}
    for p, q in combinations(probes, 2):
        isolated[p, q] = {next(iter(group)) for group in partition(zip(columns[p], columns[q], strict=True))
                          if len(group) == 1}
    covered = 0
    min_recovered = max_recovered = 0
    for first in probes:
        options = [isolated[min(first, second), max(first, second)]
                   for second in probes if second != first]
        total = low = high = 0
        for branch in partition(columns[first]):
            values = [(len(branch & option), len(branch & option & recovered)) for option in options]
            best = max(score for score, _ in values)
            tied = [selected for score, selected in values if score == best]
            total += best
            low += min(tied)
            high += max(tied)
        if total > covered:
            covered, min_recovered, max_recovered = total, low, high
        elif total == covered:
            min_recovered = min(min_recovered, low)
            max_recovered = max(max_recovered, high)
    return (covered, max(map(len, isolated.values())), min_recovered, max_recovered)


def feasible_subsets(matrix, recovered):
    probes = range(len(matrix[0]))
    full = (1 << len(matrix)) - 1
    differences = [[sum(1 << other for other, values in enumerate(matrix) if values[p] != row[p])
                    for p in probes] for row in matrix]
    fixed = total = low = high = 0
    for first in probes:
        feasible = []
        pair_scores = [0] * len(probes)
        for index, masks in enumerate(differences):
            rivals = full ^ (1 << index)
            choices = 0
            for second in probes:
                if second != first and (masks[first] | masks[second]) == rivals:
                    pair_scores[second] += 1
                    choices |= 1 << second
            if choices:
                feasible.append((full ^ masks[first], choices, index in recovered))
        fixed = max(fixed, *pair_scores)

        for size in range(len(feasible), total - 1, -1):
            realized = [sum(is_recovered for _, _, is_recovered in subset)
                        for subset in combinations(feasible, size)
                        if _can_share_tree([(branch, choices) for branch, choices, _ in subset])]
            if realized:
                if size > total:
                    total, low, high = size, min(realized), max(realized)
                else:
                    low, high = min(low, min(realized)), max(high, max(realized))
                break
    return (total, fixed, low, high)


def reconcile(matrix):
    recovered = signature_singletons(matrix, len(matrix[0])) - signature_singletons(matrix, 7)
    scores = projected(matrix, recovered)
    check(scores == feasible_subsets(matrix, recovered), "wider horizon oracle disagrees")
    return scores, len(recovered)


def run():
    widened, wider_sha = sealed(STUDY / "evidence", "wider.json")
    prior, prior_sha = sealed(STUDY / "evidence", "study.json")
    totals = dict.fromkeys(("old_adaptive", "new_adaptive", "old_fixed", "new_fixed",
                            "recovered", "recovered_min_in_optimal", "recovered_max_in_optimal"), 0)
    sources = []
    for source, before in zip(widened["sources"], prior["a02"]["sources"], strict=True):
        check(source["path"] == before["path"], "case family mismatch")
        cases = []
        for analyzed, base in zip(source["cases"], before["cases"], strict=True):
            matrix = analyzed["matrix"]
            check(analyzed["index"] == base["case"], "case ID mismatch")
            old, fixed_old, _, _ = projected([row[:7] for row in matrix], set())
            check((old, fixed_old) == (base["seven"]["A"], base["seven"]["F"]),
                  "baseline seven-probe oracle mismatch")
            (adaptive, fixed, lo, hi), recovered = reconcile(matrix)
            check(old <= adaptive and fixed_old <= fixed <= adaptive and
                  0 <= lo <= hi <= min(adaptive, recovered), "wider optimum violated")
            case = dict(zip(totals, (old, adaptive, fixed_old, fixed, recovered, lo, hi), strict=True))
            for key, value in case.items():
                totals[key] += value
            cases.append(case)
        sources.append({"path": source["path"], "cases": cases})
    check(totals["recovered"] == widened["summary"]["resolved_rows"], "missed newly unique rows")
    return {"schema": "a05.wider-horizon.v1", "protocol": PROTOCOL, "wider_sha256": wider_sha,
            "study_sha256": prior_sha, "totals": totals, "sources": sources}


if __name__ == "__main__":
    print(json.dumps(run(), separators=(",", ":")))
