import sys
import unittest
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "adaptivity"))
import decide
import epfl


class AdaptivityControls(unittest.TestCase):
    def test_packed_off_set_and_faults_match_scalar_reference(self):
        circuit = epfl.parse_blif("""# continuation and inline remarks
.model toy
.inputs a \\
b
.outputs q y r a
.names a b n
11 1
.names n b q
00 0 # OR of n and b
.names a b y
1- 1
-1 1
.names z
0
.names c
1
.names e
.names z c e r
011 0
.end
""")
        faults = (("n", 0), ("n", 1), ("q", 0), ("q", 1), ("z", 1), ("c", 0), ("e", 1))
        for a, b in product((0, 1), repeat=2):
            reference = []
            for fault_node, fault_bit in (("", 0), *faults):
                def stuck(node, value):
                    return fault_bit if node == fault_node else value

                n = stuck("n", a & b)
                q = stuck("q", n | b)
                z = stuck("z", 0)
                c = stuck("c", 1)
                e = stuck("e", 0)
                reference.append(f"{q}{a | b}{int((z, c, e) != (0, 1, 1))}{a}")
            self.assertEqual(circuit.simulate((a, b), faults), tuple(reference))

    def test_malformed_blif_blocks_simulation(self):
        header = ".model x\n.inputs a\n.outputs y\n"
        for body in (".names q y\n1 1\n.end", ".names a y\n1 x\n.end",
                     ".names a y\n1 0\n0 1\n.end", ".names a y\n1 1\n.names a y\n0 1\n.end",
                     ".names a y\n1 1\n.latch a x\n.end", ".names a y\n1 1\n.end\n\\", ".end"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                epfl.parse_blif(header + body)

    def test_replay_rejects_forged_identification_costs_and_fixed_plan(self):
        matrix = ["0000000"] * 8
        trials = [dict(trace=[0, 1], fixed=[0, 1], selected=False, accesses=100, reads=48)
                  for _ in matrix]
        self.assertEqual(decide.replay(matrix, "fixed", trials), 0)
        for change, expected in (({"selected": True}, "invalid claim"),
                                 ({"accesses": 385}, "invalid resource"),
                                 ({"reads": 47}, "invalid resource"),
                                 ({"trace": [0, 2]}, "fixed plan changed"),
                                 ({"trace": [0]}, "fixed plan abandoned")):
            tampered = trials[:-1] + [dict(trials[-1], **change)]
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, expected):
                decide.replay(matrix, "fixed", tampered)
