import base64
import copy
import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from tools import render_research_atlas as atlas


class ResearchAtlasTest(unittest.TestCase):
    def setUp(self):
        self.data = atlas.load_manifest()

    def test_manifest_rejects_decoded_duplicate_keys(self):
        raw = r'{"schema":"first","\u0073chema":"second"}'
        with patch.object(Path, "read_text", return_value=raw):
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
                atlas.load_manifest()

    def test_repeated_route_is_verified_once_and_false_sibling_never_passes(self):
        project = self.data["projects"][0]
        reference = project["files"]["inspect"]
        payload = b"content"
        reference["blob"] = hashlib.sha1(b"blob 7\0" + payload, usedforsecurity=False).hexdigest()
        project["files"] = {role: dict(reference) for role in atlas.ROLES}
        response = {"type": "file", "path": reference["path"], "encoding": "base64",
                    "sha": reference["blob"], "size": len(payload),
                    "content": base64.b64encode(payload).decode("ascii")}
        self.data["projects"] = [project]
        with patch.object(atlas, "urlopen", return_value=io.BytesIO(
            json.dumps(response).encode()
        )) as request, redirect_stdout(io.StringIO()):
            atlas.verify_remote(self.data)
            request.assert_called_once()

        project["files"]["boundary"]["blob"] = "0" * 40
        with patch.object(Path, "read_text", return_value=json.dumps(self.data)):
            with self.assertRaisesRegex(ValueError, "Conflicting blob declarations"):
                atlas.load_manifest()
        with patch.object(atlas, "urlopen") as request:
            with self.assertRaisesRegex(ValueError, "Conflicting blob declarations"):
                atlas.verify_remote(self.data)
            request.assert_not_called()

    def test_remote_verification_failure_does_not_write_any_output(self):
        with (
            patch.object(sys, "argv", ["atlas", "--verify-remote"]),
            patch.object(atlas, "verify_remote", side_effect=ValueError("remote mismatch")),
            patch.object(Path, "mkdir") as mkdir,
            patch.object(Path, "write_bytes") as write,
        ):
            with self.assertRaisesRegex(ValueError, "remote mismatch"):
                atlas.main()
            mkdir.assert_not_called()
            write.assert_not_called()

    def test_manifest_rejects_drift_in_date_claim_scope_and_canonical_path(self):
        changes = (
            ("date", lambda data: data.update(verified_date="2026-02-30")),
            ("scope", lambda data: data.update(verification_scope="Experiments executed.")),
            ("path", lambda data: data["projects"][0]["files"]["inspect"].update(path="docs//./model.md")),
            ("repository", lambda data: data["projects"][0].update(repository="neuron7x/..")),
        )
        for label, change in changes:
            with self.subTest(label=label):
                data = copy.deepcopy(self.data)
                change(data)
                with patch.object(Path, "read_text", return_value=json.dumps(data)):
                    with self.assertRaises(ValueError):
                        atlas.load_manifest()

    def test_matching_sha_metadata_cannot_hide_wrong_content_or_path(self):
        project = self.data["projects"][0]
        reference = project["files"]["inspect"]
        payload = b"x"
        reference["blob"] = hashlib.sha1(b"blob 1\0x", usedforsecurity=False).hexdigest()
        project["files"] = {role: dict(reference) for role in atlas.ROLES}
        self.data["projects"] = [project]
        response = {"type": "file", "path": reference["path"], "encoding": "base64",
                    "sha": reference["blob"], "size": len(payload), "content": "eA=="}
        for change in [
            {"path": "different.md"}, {"type": "symlink"}, {"submodule_git_url": "present"},
            {"size": True}, {"size": 2}, {"content": "eQ=="}, {"content": "not base64"},
        ]:
            with self.subTest(change=change):
                raw = json.dumps({**response, **change}).encode()
                with patch.object(atlas, "urlopen", return_value=io.BytesIO(raw)):
                    with self.assertRaises(ValueError):
                        atlas.verify_remote(self.data)

    def test_shared_visual_label_contract(self):
        fixtures = Path(__file__).parent / "fixtures" / "atlas_labels.json"
        for case in json.loads(fixtures.read_text()):
            with self.subTest(field=case["field"], value=case["value"]):
                data = copy.deepcopy(self.data)
                data["projects"][0][case["field"]] = case["value"]
                with patch.object(Path, "read_text", return_value=json.dumps(data)):
                    if case["valid"]:
                        accepted = atlas.load_manifest()
                        ElementTree.fromstring(atlas.svg(accepted, "dark", True))
                    else:
                        with self.assertRaises(ValueError):
                            atlas.load_manifest()
