"""Independent A03 oracle using rival disagreement and feasible row subsets."""

from collections.abc import Sequence
from itertools import combinations

Category = str | int


def _can_share_tree(continuations: Sequence[tuple[int, int]]) -> bool:
    common: dict[int, int] = {}
    for branch, choices in continuations:
        available = common.get(branch, choices) & choices
        if not available:
            return False
        common[branch] = available
    return True


def oracle(matrix: Sequence[Sequence[Category]]) -> dict[str, int]:
    """Return A03 identification limits for a complete 2–8 by 2–7 table."""
    if not 2 <= len(matrix) <= 8:
        raise ValueError("expected between two and eight hypotheses")
    probes = range(len(matrix[0]))
    if not 2 <= len(probes) <= 7 or any(len(row) != len(probes) for row in matrix):
        raise ValueError("expected between two and seven equally many probes per hypothesis")
    if any(type(outcome) not in (str, int) for row in matrix for outcome in row):
        raise ValueError("expected string or integer probe outcomes")

    all_rows = (1 << len(matrix)) - 1
    rivals = [all_rows ^ (1 << row) for row in range(len(matrix))]
    disagreements = []
    unique = 0
    for row, rival in zip(matrix, rivals, strict=True):
        masks = [
            sum(1 << j for j, other in enumerate(matrix) if row[probe] != other[probe])
            for probe in probes
        ]
        disagreements.append(masks)
        separated = 0
        for mask in masks:
            separated |= mask
        unique += separated == rival

    witnesses: set[int] = set()
    best_root = adaptive = 0
    for first in probes:
        options = []
        for row, masks in enumerate(disagreements):
            # Every rival must disagree on the first or the second answer.
            choices = sum(
                1 << second
                for second in probes
                if second != first and (masks[first] | masks[second]) == rivals[row]
            )
            if choices:
                witnesses.add(row)
                # Rows agreeing on the root have the same branch bitmask.
                options.append((all_rows ^ masks[first], choices))
        best_root = max(best_root, len(options))

        # A root is feasible for a requested subset exactly when every branch
        # has a common second probe. Already isolated rows allow all seconds.
        for size in range(len(options), adaptive, -1):
            if any(_can_share_tree(subset) for subset in combinations(options, size)):
                adaptive = size
                break

    fixed = max(
        sum((masks[first] | masks[second]) == rival
            for masks, rival in zip(disagreements, rivals, strict=True))
        for first, second in combinations(probes, 2)
    )
    return {"U": unique, "W": len(witnesses), "K": best_root, "A": adaptive, "F": fixed}
