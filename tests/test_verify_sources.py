import hashlib
import sys
import unittest
from unittest.mock import patch

from tools import verify_sources as source


class SourceProofTest(unittest.TestCase):
    def test_raw_commit_is_bound_to_its_root_tree_bytes(self):
        tree = "a" * 40
        raw = f"tree {tree}\n\nA fixture commit\n".encode("ascii")
        digest = hashlib.sha1(f"commit {len(raw)}\0".encode() + raw, usedforsecurity=False).hexdigest()
        self.assertEqual(source.checked_commit_tree(raw, digest), tree)
        with self.assertRaisesRegex(source.SourceError, "commit hash mismatch"):
            source.checked_commit_tree(raw.replace(b"tree a", b"tree b"), digest)

    def test_wrong_active_login_stops_before_any_source_read(self):
        with (patch.object(source, "gh_object", return_value={"login": "someone-else"}),
              patch.object(source, "read_commit_tree") as git):
            with self.assertRaisesRegex(source.SourceError, "login must be"):
                source.verify_pins({"projects": []}, {})
            git.assert_not_called()

    def test_github_root_must_match_the_native_commit_root(self):
        data = {"projects": [{"repository": "neuron7x/sample", "commit": "a" * 40}]}
        report = {"source_requests": 0}
        def verify(_, fetch):
            fetch("neuron7x/sample", "git/commits/" + "a" * 40)
        with (patch.object(source, "require_owner"),
              patch.object(source, "read_commit_tree", return_value="b" * 40),
              patch.object(source, "gh_object", return_value={"tree": {"sha": "c" * 40}}),
              patch.object(source.atlas, "verify_remote", side_effect=verify)):
            with self.assertRaisesRegex(source.SourceError, "root differs"):
                source.verify_pins(data, report)
        self.assertEqual(report["source_requests"], 1)
        self.assertNotIn("blobs_verified", report)

    def test_transport_closes_on_oversized_read(self):
        command = [sys.executable, "-c", "print('x' * 4096)"]
        with self.assertRaisesRegex(source.SourceError, "byte limit"):
            source.bounded_command(command, 5, 12)
