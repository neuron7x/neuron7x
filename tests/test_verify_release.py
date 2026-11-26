import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import verify_release as gate


class ReleaseArchiveTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="release-archive-test-")
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name) / "repo"
        self.repo.mkdir()
        self.archive = Path(temp.name) / "archive"
        self.archive.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Archive fixture")
        self.git("config", "user.email", "fixture@invalid.invalid")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *arguments):
        return subprocess.check_output(["git", *arguments], cwd=self.repo, env=gate.VERIFY_ENV).strip().decode()

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "Archive fixture")
        return self.git("rev-parse", "HEAD")

    def test_archive_matches_regular_and_executable_blobs(self):
        (self.repo / "proof.txt").write_text("exact source")
        tool = self.repo / "tool.sh"
        tool.write_text("#!/bin/sh\n")
        tool.chmod(0o755)
        commit = self.commit()
        with patch.object(gate, "ROOT", self.repo):
            self.assertEqual(gate.extract_commit(commit, self.archive), 2)
        self.assertEqual((self.archive / "proof.txt").read_text(), "exact source")
        self.assertEqual((self.archive / "tool.sh").stat().st_mode & 0o777, 0o755)

    def test_archive_rejects_tracked_file_hidden_by_local_attributes(self):
        (self.repo / "proof.txt").write_text("tracked evidence")
        (self.repo / "keep.txt").write_text("present")
        commit = self.commit()
        (self.repo / ".git/info/attributes").write_text("proof.txt export-ignore\n")
        with patch.object(gate, "ROOT", self.repo):
            with self.assertRaisesRegex(gate.VerificationError, "Archive omits Git tree paths: proof.txt"):
                gate.extract_commit(commit, self.archive)

    def test_archive_rejects_substituted_bytes(self):
        (self.repo / "proof.txt").write_text("$Format:%H$")
        (self.repo / ".gitattributes").write_text("proof.txt export-subst\n")
        commit = self.commit()
        with patch.object(gate, "ROOT", self.repo):
            with self.assertRaisesRegex(gate.VerificationError, "Archive bytes differ from Git tree: proof.txt"):
                gate.extract_commit(commit, self.archive)

    def test_runner_must_match_the_revision(self):
        selected = self.archive / "tools"
        selected.mkdir()
        script = selected / "verify_release.py"
        script.write_bytes(Path(gate.__file__).read_bytes())
        gate.require_committed_verifier(self.archive)
        script.write_bytes(script.read_bytes() + b"\n")
        with self.assertRaisesRegex(gate.VerificationError, "Verifier differs"):
            gate.require_committed_verifier(self.archive)

    def test_git_replace_does_not_change_the_verified_revision(self):
        file = self.repo / "proof.txt"
        file.write_text("first")
        original = self.commit()
        file.write_text("second")
        substitute = self.commit()
        self.git("replace", original, substitute)
        with patch.object(gate, "ROOT", self.repo):
            self.assertEqual(gate.extract_commit(original, self.archive), 1)
        self.assertEqual((self.archive / "proof.txt").read_text(), "first")

    def test_machine_report_marks_unverified_commit_without_fake_coverage(self):
        report = self.archive / "result.json"
        with (
            patch.object(gate, "ROOT", self.repo),
            patch.object(sys, "argv", ["gate", "missing", "--report", str(report)]),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(gate.main(), 1)
        observed = json.loads(report.read_text())
        self.assertEqual(observed["status"], "FAIL")
        self.assertEqual(observed["failed_stage"], "resolve-commit")
        self.assertIsNone(observed["commit"])
        self.assertEqual(observed["checks"], [])
        self.assertEqual(observed["negative_controls"], {"passed": 0, "failed": 0})

    def test_attempted_negative_control_needs_its_diagnostic_to_pass(self):
        records = []
        outcome = subprocess.CompletedProcess([], 1, "wrong diagnostic", "")
        with patch.object(gate, "execute", return_value=outcome), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(gate.VerificationError):
                gate.run_check(records, "control", ["example"], self.repo, 1,
                               lambda result: result.stdout == "expected diagnostic")
        self.assertEqual(records, [{"name": "control", "kind": "negative-control",
                                    "expected_exit": 1, "actual_exit": 1, "status": "FAIL"}])

    def test_positive_suite_checks_reject_incomplete_or_contradictory_output(self):
        full = ("TAP version 13\nok 1 - sample\n1..1\n# tests 1\n# suites 0\n"
                "# pass 1\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n# duration_ms 1.2\n")
        self.assertTrue(gate.node_suite(subprocess.CompletedProcess([], 0, full, "")))
        for text in ["# tests 1\n# pass 1\n", full.replace("# fail 0", "# fail 1"),
                     full.replace("# skipped 0", "# skipped 1"), full.replace("ok 1", "ok 2"),
                     full.replace("ok 1", "not ok 1 - hidden failure\nok 1"),
                     full.replace("1..1", "1.." + "9" * 4400),
                     full.replace("sample", "sample # SKIP"),
                     full.replace("# tests 1", "# tests 100").replace("# pass 1", "# pass 100")]:
            self.assertFalse(gate.node_suite(subprocess.CompletedProcess([], 0, text, "")))
        python = "-" * 70 + "\nRan 1 test in 0.001s\n\nOK\n"
        self.assertTrue(gate.python_suite(subprocess.CompletedProcess([], 0, "", python)))
        for text in [python.replace("0.001s", "wrong"), "Ran 2 tests in 0.001s\n" + python]:
            self.assertFalse(gate.python_suite(subprocess.CompletedProcess([], 0, "", text)))
