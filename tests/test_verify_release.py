import subprocess
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
