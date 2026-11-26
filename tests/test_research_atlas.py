import base64
import copy
import hashlib
import io
import json
import sys
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote
from xml.etree import ElementTree

from tools import render_research_atlas as atlas


class ResearchAtlasTest(unittest.TestCase):
    def setUp(self):
        self.data = atlas.load_manifest()

    def remote_objects(self, project, response, file_mode="100644"):
        path = response["path"]
        parts = path.split("/")
        repository = project["repository"]
        commit = project["commit"]
        host = f"https://api.github.com/repos/{repository}/"
        contents_url = host + f"contents/{quote(path, safe='/')}?ref={commit}"
        trees = []
        oid = response["sha"]
        for index in range(len(parts) - 1, -1, -1):
            part = parts[index]
            mode = file_mode if index == len(parts) - 1 else "040000"
            kind = "tree" if mode == "040000" else "commit" if mode == "160000" else "blob"
            raw = mode.lstrip("0").encode() + b" " + part.encode() + b"\0" + bytes.fromhex(oid)
            actual = hashlib.sha1(f"tree {len(raw)}\0".encode() + raw, usedforsecurity=False).hexdigest()
            trees.append((host + f"git/trees/{actual}", {
                "sha": actual, "truncated": False,
                "tree": [{"path": part, "type": kind, "mode": mode, "sha": oid}],
            }))
            oid = actual
        return {
            host + f"git/commits/{commit}": {"sha": commit, "tree": {"sha": oid}},
            **dict(reversed(trees)),
            contents_url: response,
        }

    @staticmethod
    def serve(objects):
        return lambda request, timeout: io.BytesIO(json.dumps(objects[request.full_url]).encode())

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
        objects = self.remote_objects(project, response)
        with patch.object(atlas, "urlopen", side_effect=self.serve(objects)) as request, redirect_stdout(io.StringIO()):
            atlas.verify_remote(self.data)
            self.assertEqual(request.call_count, len(objects))

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
                objects = self.remote_objects(project, response)
                url = next(url for url in objects if "/contents/" in url)
                objects[url] = {**response, **change}
                with patch.object(atlas, "urlopen", side_effect=self.serve(objects)):
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

    def test_route_label_cannot_add_a_second_link(self):
        project = self.data["projects"][0]
        project["probe_kind"] = "Check](https://outside.invalid)[More"
        rendered = atlas.document(self.data)
        row = next(line for line in rendered.splitlines() if line.startswith("| Falsify |"))
        self.assertIn(r"Check\](https://outside.invalid)\[More", row)
        self.assertIn(atlas.source_url(project, "falsify"), row)
        project["probe_kind"] = "Check\nOther"
        with patch.object(Path, "read_text", return_value=json.dumps(self.data)):
            with self.assertRaisesRegex(ValueError, "Invalid probe label"):
                atlas.load_manifest()

    def test_commit_tree_requires_regular_leaf_before_content_is_requested(self):
        project = self.data["projects"][0]
        blob = hashlib.sha1(b"blob 1\0x", usedforsecurity=False).hexdigest()
        path = "docs/proof.md"
        reference = {"path": path, "blob": blob}
        project["files"] = {role: dict(reference) for role in atlas.ROLES}
        self.data["projects"] = [project]
        response = {"type": "file", "path": path, "encoding": "base64",
                    "sha": blob, "size": 1, "content": "eA=="}
        objects = self.remote_objects(project, response, "100755")
        with patch.object(atlas, "urlopen", side_effect=self.serve(objects)), redirect_stdout(io.StringIO()):
            atlas.verify_remote(self.data)
        for label, mode in [("symlink", "120000"), ("gitlink", "160000")]:
            with self.subTest(label=label):
                changed = self.remote_objects(project, response, mode)
                with patch.object(atlas, "urlopen", side_effect=self.serve(changed)) as request:
                    with self.assertRaisesRegex(ValueError, "Source tree path mismatch"):
                        atlas.verify_remote(self.data)
                    self.assertFalse(any("/contents/" in call.args[0].full_url for call in request.call_args_list))
        for label, mutate in [
            ("truncated", lambda root, leaf: leaf.update(truncated=True)),
            ("duplicate", lambda root, leaf: leaf["tree"].append(dict(leaf["tree"][0]))),
            ("wrong blob", lambda root, leaf: leaf["tree"][0].update(sha="0" * 40)),
            ("non-tree parent", lambda root, leaf: root["tree"][0].update(mode="120000")),
            ("missing entry", lambda root, leaf: leaf.update(tree=[])),
        ]:
            with self.subTest(label=label):
                changed = copy.deepcopy(objects)
                root, leaf = [record for url, record in changed.items() if "/git/trees/" in url]
                mutate(root, leaf)
                with patch.object(atlas, "urlopen", side_effect=self.serve(changed)) as request:
                    with self.assertRaises(ValueError):
                        atlas.verify_remote(self.data)
                    self.assertFalse(any("/contents/" in call.args[0].full_url for call in request.call_args_list))

    def test_tree_hash_matches_git_sorting_and_detects_unrelated_entry_changes(self):
        entries = [
            {"mode": "100755", "type": "blob", "sha": "a" * 40, "path": "foo0"},
            {"mode": "040000", "type": "tree", "sha": "b" * 40, "path": "foo"},
            {"mode": "100644", "type": "blob", "sha": "c" * 40, "path": "foo.bar"},
        ]
        records = b"".join(
            f"{e['mode']} {e['type']} {e['sha']}\t{e['path']}\0".encode() for e in entries
        )
        with tempfile.TemporaryDirectory(prefix="github-tree-test-") as directory:
            subprocess.run(["git", "init", "-q", "--object-format=sha1"], cwd=directory, check=True)
            sha = subprocess.check_output(["git", "mktree", "-z", "--missing"], cwd=directory,
                                          input=records).decode().strip()
        self.assertEqual(set(atlas.verified_tree_entries(entries, sha)), {"foo", "foo0", "foo.bar"})
        changed = copy.deepcopy(entries)
        changed[0]["path"] = "other"
        with self.assertRaisesRegex(ValueError, "Git tree bytes mismatch"):
            atlas.verified_tree_entries(changed, sha)
