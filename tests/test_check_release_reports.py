import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools import check_release_reports as checker


IDENTITY = ("a" * 40, "b" * 40, "c" * 64, 52)


def report_fixture():
    rows = []
    for kind, names in checker.EXPECTED.items():
        code = 0 if kind == "check" else 1
        rows.extend({"name": name, "kind": kind, "expected_exit": code, "actual_exit": code, "status": "PASS"}
                    for name in sorted(names))
    commit, tree, verifier, blobs = IDENTITY
    return {"schema": "neuron7x.release-verification.v1", "status": "PASS", "failed_stage": None,
            "commit": commit, "tree": tree, "tracked_blobs_verified": blobs, "verifier_sha256": verifier,
            "checks": rows, "negative_controls": {"passed": len(checker.EXPECTED["negative-control"]), "failed": 0}}


class ReportComparisonTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="release-report-test-")
        self.addCleanup(temp.cleanup)
        self.first = Path(temp.name) / "first.json"
        self.second = Path(temp.name) / "second.json"

    @staticmethod
    def write(path, report):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_identical_canonical_reports_return_their_digest(self):
        for path in (self.first, self.second):
            self.write(path, report_fixture())
        self.assertEqual(checker.compare(self.first, self.second, IDENTITY),
                         hashlib.sha256(self.first.read_bytes()).hexdigest())

    def test_individually_valid_reports_with_different_order_are_refused(self):
        front = report_fixture()
        back = copy.deepcopy(front)
        back["checks"].reverse()
        checker.validate(front, *IDENTITY)
        checker.validate(back, *IDENTITY)
        self.write(self.first, front)
        self.write(self.second, back)
        with self.assertRaisesRegex(ValueError, "reports differ"):
            checker.compare(self.first, self.second, IDENTITY)

    def test_two_paths_to_one_report_do_not_count_as_two_artifacts(self):
        self.write(self.first, report_fixture())
        os.link(self.first, self.second)
        with self.assertRaisesRegex(ValueError, "distinct report files"):
            checker.compare(self.first, self.second, IDENTITY)

    def test_identical_but_invalid_proofs_never_pass(self):
        for change in ("missing", "foreign", "boolean", "duplicate", "wrong sha"):
            with self.subTest(change=change):
                report = report_fixture()
                if change == "missing":
                    report["checks"].pop()
                    report["negative_controls"]["passed"] -= 1
                elif change == "foreign":
                    report["checks"][-1]["name"] = "fabricated"
                elif change == "boolean":
                    report["checks"][-1]["actual_exit"] = True
                elif change == "duplicate":
                    report["checks"][-1] = copy.deepcopy(report["checks"][-2])
                else:
                    report["commit"] = "d" * 40
                for path in (self.first, self.second):
                    self.write(path, report)
                with self.assertRaises(ValueError):
                    checker.compare(self.first, self.second, IDENTITY)

    def test_duplicate_keys_cannot_be_hidden_in_matching_json(self):
        self.write(self.first, report_fixture())
        altered = self.first.read_text().replace('  "status": "PASS",', '  "status": "FAIL",\n  "status": "PASS",')
        self.first.write_text(altered)
        self.second.write_text(altered)
        with self.assertRaisesRegex(ValueError, "Noncanonical"):
            checker.compare(self.first, self.second, IDENTITY)
