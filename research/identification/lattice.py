"""Exact limits for two noiseless probes across a finite categorical catalog."""
from collections import Counter, defaultdict
from itertools import combinations

FIELDS = ("U", "W", "K", "A", "F")
GAPS = ("aliases", "horizon", "shared_root", "shared_branch", "sealed_probe", "adaptivity")


def partition(labels):
    blocks = defaultdict(set)
    for index, label in enumerate(labels):
        blocks[label].add(index)
    return tuple(blocks.values())


def measure(matrix):
    if len(matrix) < 2 or len(matrix[0]) < 2 or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError("expected a rectangular catalog with at least two models and probes")
    columns = tuple(zip(*matrix, strict=True))
    probes = range(len(columns))
    witnesses = {}
    for p, q in combinations(probes, 2):
        witnesses[p, q] = {next(iter(block)) for block in partition(zip(columns[p], columns[q], strict=True))
                           if len(block) == 1}

    coverage = set().union(*witnesses.values())
    usable_by_root = []
    scores = []
    for first in probes:
        options = [witnesses[min(first, second), max(first, second)]
                   for second in probes if second != first]
        usable_by_root.append(len(set().union(*options)))
        scores.append(sum(max(len(indices & option) for option in options)
                          for indices in partition(columns[first])))

    counts = Counter(tuple(row) for row in matrix)
    return {"U": sum(value == 1 for value in counts.values()), "W": len(coverage),
            "K": max(usable_by_root), "A": max(scores), "F": max(map(len, witnesses.values()))}


def gaps(n, observable, available):
    absolute = [n, *(observable[key] for key in FIELDS)]
    policy = [n, *(available[key] for key in FIELDS)]
    if any(left < right for chain in (absolute, policy)
           for left, right in zip(chain, chain[1:])):
        raise ValueError("identification order violated")
    if any(observable[key] < available[key] for key in FIELDS):
        raise ValueError("additional probe lowered limit")
    boundaries = [n, observable["U"], observable["W"], observable["K"],
                  observable["A"], available["A"], available["F"]]
    return dict(zip(GAPS, (left - right for left, right in zip(boundaries, boundaries[1:])),
                    strict=True))
