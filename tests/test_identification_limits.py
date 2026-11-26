import sys
import unittest
from itertools import combinations, product
from pathlib import Path
from random import Random

STUDY = Path(__file__).resolve().parents[1] / "research" / "identification"
sys.path.insert(0, str(STUDY))
from lattice import gaps, measure
from subset_oracle import oracle


def direct_tree(matrix):
    probes = range(len(matrix[0]))
    best = 0
    for root in probes:
        outcomes = tuple(sorted({row[root] for row in matrix}))
        for seconds in product([probe for probe in probes if probe != root], repeat=len(outcomes)):
            policy = dict(zip(outcomes, seconds, strict=True))
            paths = [(row[root], row[policy[row[root]]]) for row in matrix]
            best = max(best, sum(paths.count(path) == 1 for path in paths))
    return best


class IdentificationLimits(unittest.TestCase):
    def test_each_strict_bound_has_a_pure_counterexample(self):
        controls = (
            (["00", "00"], (0, 0, 0, 0, 0)),
            (list(product("01", repeat=3)), (8, 0, 0, 0, 0)),
            (["0000", "0001", "0010", "0111", "1011", "1111"], (6, 6, 3, 3, 3)),
            (["1000", "0100", "0010", "0001"], (4, 4, 4, 2, 2)),
            (["000", "010", "100", "101"], (4, 4, 4, 4, 2)),
        )
        for matrix, expected in controls:
            with self.subTest(matrix=matrix):
                self.assertEqual(tuple(measure(matrix).values()), expected)
                self.assertEqual(tuple(oracle(matrix).values()), expected)

    def test_all_three_solvers_agree_on_categorical_trees_and_relabelings(self):
        rng = Random(9173)
        for _ in range(1200):
            n, k, alphabet = rng.randrange(2, 9), rng.randrange(2, 5), rng.randrange(2, 4)
            matrix = [tuple(rng.randrange(alphabet) for _ in range(k)) for _ in range(n)]
            expected = measure(matrix)
            self.assertEqual(oracle(matrix), expected)
            self.assertEqual(direct_tree(matrix), expected["A"])
            columns = rng.sample(range(k), k)
            relabeled = [(tuple(f"{probe}:{(row[probe]+1)%alphabet}" for probe in columns))
                         for row in rng.sample(matrix, n)]
            self.assertEqual(measure(relabeled), expected)
            self.assertEqual(oracle(relabeled), expected)

    def test_sealed_probe_gives_no_policy_credit_and_a_duplicate_changes_no_bound(self):
        matrix = [f"000000{outcome}" for outcome in range(8)]
        six, seven = measure([row[:6] for row in matrix]), measure(matrix)
        self.assertEqual(sum(seven.values()), 40)
        self.assertEqual(gaps(8, seven, six),
                         dict(aliases=0, horizon=0, shared_root=0, shared_branch=0,
                              sealed_probe=8, adaptivity=0))
        table = ["000", "010", "100", "101"]
        self.assertEqual(measure(table), measure([row + row[1] for row in table]))

    def test_randomization_changes_uniform_one_hot_fairness_without_raising_coverage(self):
        one_hot = ["1000", "0100", "0010", "0001"]
        pairs = tuple(combinations(range(4), 2))
        identified = [0] * 4
        for pair in pairs:
            outcomes = [tuple(row[probe] for probe in pair) for row in one_hot]
            for index, outcome in enumerate(outcomes):
                identified[index] += outcomes.count(outcome) == 1
        self.assertEqual(identified, [len(pairs) // 2] * 4)
        self.assertEqual(measure(one_hot)["A"], 2)


class WiderObservations(unittest.TestCase):
    def test_packed_faults_match_scalar_across_every_primitive(self):
        from wider import packed
        from iscas import parse

        circuit = parse("""
module toy (a,b,c,d,e,f,g,h,i);
input a,b;
output c,d,e,f,g,h,i;
and U1 (c,a,b);
nand U2 (d,a,b);
or U3 (e,c,d);
nor U4 (f,a,b);
xor U5 (g,d,f);
buf U6 (h,g);
not U7 (i,h);
endmodule
""", "toy")
        vectors = list(product((0, 1), repeat=2))
        faults = tuple((node, index % 2) for index, node in enumerate(circuit.nodes))
        actual = packed(circuit, vectors, faults)
        separate = zip(*(circuit.simulate(vector, faults) for vector in vectors), strict=True)
        self.assertEqual([tuple(row) for row in actual], list(separate))
