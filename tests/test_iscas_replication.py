import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from graphlib import CycleError
from itertools import product
from pathlib import Path

REPLICATION = Path(__file__).resolve().parents[1] / "research" / "adaptivity" / "replication"
sys.path.insert(0, str(REPLICATION))
from iscas import parse
from run import compare, decision, summarize

TOY = """
module toy (a,b,x,y);
input a,b;
output y,x;
wire n;
nand U2 (x,n,b);
nor U3 (y,x,a);
xor U1 (n,a,b);
endmodule
"""


class TransferControls(unittest.TestCase):
    def test_gate_order_fault_propagation_and_output_order(self):
        circuit = parse(TOY, "toy")
        for a, b in product((0, 1), repeat=2):
            healthy = (a + b) % 2
            expected = []
            for n in (healthy, 0, 1):
                x = int(not (n & b))
                y = int(not (x | a))
                expected.append(f"{y}{x}")
            self.assertEqual(circuit.simulate((a, b), [("n", 0), ("n", 1)]), tuple(expected))

    def test_reject_cycle_missing_driver_and_duplicate_signal(self):
        with self.assertRaises(CycleError):
            parse(TOY.replace("xor U1 (n,a,b)", "xor U1 (n,x,b)"), "toy")
        for wrong in (TOY.replace("n,a,b", "n,c,b"), TOY.replace("output y,x", "output y,y"),
                      TOY.replace("xor U1 (n,a,b)", "always U1 (n,a,b)")):
            with self.assertRaises(ValueError):
                parse(wrong, "toy")

    def test_threshold_and_intersection_are_strict(self):
        cases = (("1/20", "1/20", "REFUTED_PRACTICAL_ADVANTAGE_A02"),
                 ("1/20", "2/20", "INCONCLUSIVE_A02"), ("2/20", "2/20", "SUPPORT_A02"))
        for low, high, expected in cases:
            self.assertEqual(decision({"other": {"interval":["1/2", "1/2"]},
                                       "trial": {"interval":[low, high]}}), expected)



class TransferArchive(unittest.TestCase):
    def test_sealed_panel_replays_every_trace_and_the_frozen_decision(self):
        evidence = REPLICATION / "evidence"
        index = [line.split("  ") for line in (evidence / "SHA256SUMS").read_text().splitlines()]
        self.assertEqual([item[1] for item in index], ["inputs.json", "traces.json", "result.json"])
        artifacts = {}
        for digest, name in index:
            payload = ((evidence / name).read_bytes() if name == "result.json" else
                       gzip.decompress((evidence / (name + ".gz")).read_bytes()))
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)
            artifacts[name] = payload
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inputs.json"
            path.write_bytes(artifacts["inputs.json"])
            self.assertEqual(compare(path), artifacts["traces.json"])
        actual = summarize(artifacts["inputs.json"], artifacts["traces.json"])
        self.assertEqual(actual, json.loads(artifacts["result.json"]))
        self.assertEqual(actual["decision"], "INCONCLUSIVE_A02")
