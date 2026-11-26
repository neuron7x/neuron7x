import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research" / "adaptivity"
sys.path.insert(0, str(STUDY))
import audit


class AdaptivityArchive(unittest.TestCase):
    def test_anchored_panel_reproduces_all_policy_traces_and_decisions(self):
        evidence = STUDY / "evidence"
        filenames = ("inputs.json", "traces.json", "ec2.json", "decision.json", "audit.json")
        manifest = [line.split("  ") for line in (evidence / "SHA256SUMS").read_text().splitlines()]
        self.assertEqual(tuple(name for _, name in manifest), filenames)
        artifacts = {}
        for sha, name in manifest:
            if name in filenames[:3]:
                payload = gzip.decompress((evidence / (name + ".gz")).read_bytes())
            else:
                payload = (evidence / name).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), sha)
            artifacts[name] = payload
        panel = json.loads(artifacts["inputs.json"])
        self.assertEqual(panel["protocol"], "1d24e98aec1df58814544dcaadd2c672df853612")
        self.assertEqual(panel["upstream"], "82d8cc6910419298e713a46644ed59fd3df53038")
        with tempfile.TemporaryDirectory() as directory:
            matrix = Path(directory) / "inputs.json"
            matrix.write_bytes(artifacts["inputs.json"])
            for script, filename in (("evaluate.mjs", "traces.json"), ("ec2.mjs", "ec2.json")):
                output = subprocess.run(["node", str(STUDY / script), str(matrix)], check=True,
                                        capture_output=True, timeout=20).stdout
                self.assertEqual(output, artifacts[filename], filename)

        checked = audit.audit(*(artifacts[name] for name in filenames[:3]))
        self.assertEqual(checked, json.loads(artifacts["audit.json"]))
        self.assertEqual(audit.summarize(*(artifacts[name] for name in filenames[:2])),
                         json.loads(artifacts["decision.json"]))

    def test_auditor_rejects_truth_leak_and_starved_comparators(self):
        matrix = [[str(int(row == probe)) for probe in range(7)] for row in range(8)]
        exact = {"trace": [0, 1], "fixed": None, "selected": False, "accesses": 56, "reads": 48}
        fixed = {**exact, "fixed": []}
        starved = [dict(fixed, trace=[]) for _ in range(8)]
        comparator = [dict(exact, trace=[0] if row == 0 else [0, 1], selected=row < 2)
                      for row in range(8)]
        candidate = {name: comparator for name in audit.POLICIES}
        candidate["exact"] = [dict(exact, trace=[row] if row < 6 else [], selected=row < 6)
                              for row in range(8)]
        candidate["fixed"] = starved
        with self.assertRaisesRegex(ValueError, "enumerated bound"):
            audit.audit_case(matrix, {"bound": 6, "fullBound": 6, "policies": candidate}, comparator)
        candidate["exact"] = comparator
        with self.assertRaisesRegex(ValueError, "fixed plan is not optimal"):
            audit.audit_case(matrix, {"bound": 2, "fullBound": 2, "policies": candidate}, comparator)
        candidate["fixed"] = [dict(trial, fixed=[0, 1]) for trial in comparator]
        candidate["pairs"] = [dict(trial, trace=[], selected=False) for trial in comparator]
        with self.assertRaisesRegex(ValueError, "pairs action disagrees"):
            audit.audit_case(matrix, {"bound": 2, "fullBound": 2, "policies": candidate}, comparator)
