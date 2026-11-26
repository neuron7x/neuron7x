"""Verify pinned commit, tree and blob bytes through an existing neuron7x login."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import render_research_atlas as atlas
from . import verify_release as release

OWNER = "neuron7x"
REPOSITORY = re.compile(r"neuron7x/[A-Za-z0-9_.-]+")
OBJECT_LIMIT = 8 * 1024 * 1024
AUTH_ENV = {key: value for key, value in release.VERIFY_ENV.items()
            if key not in {"GH_DEBUG", "GIT_TRACE_CURL", "GIT_CURL_VERBOSE"}}
AUTH_ENV.update(GH_PROMPT_DISABLED="1", GIT_TERMINAL_PROMPT="0")


class SourceError(Exception):
    pass


def bounded_command(command: list[str], timeout: int, limit: int = OBJECT_LIMIT) -> bytes:
    deadline = time.monotonic() + timeout
    result = bytearray()
    with (
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=AUTH_ENV) as child,
        selectors.DefaultSelector() as ready,
    ):
        try:
            ready.register(child.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not ready.select(remaining):
                    raise SourceError(f"Read timed out: {command[0]}")
                chunk = os.read(child.stdout.fileno(), min(65536, limit + 1 - len(result)))
                if not chunk:
                    break
                result.extend(chunk)
                if len(result) > limit:
                    raise SourceError(f"Read exceeded byte limit: {command[0]}")
            if child.wait(timeout=max(0, deadline - time.monotonic())) != 0:
                raise SourceError(f"Read command failed: {command[0]} {command[-1]}")
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
    return bytes(result)


def gh_object(route: str) -> dict:
    raw = bounded_command(["gh", "api", "--hostname", "github.com", "--method", "GET",
                           "-H", "Accept: application/vnd.github+json", route], 20)
    data = json.loads(raw, object_pairs_hook=atlas.unique_json_object)
    if not isinstance(data, dict):
        raise SourceError("Expected one GitHub object")
    return data


def require_owner() -> None:
    if gh_object("user").get("login") != OWNER:
        raise SourceError(f"GitHub login must be {OWNER}")


def checked_repository(repository: str) -> None:
    if not REPOSITORY.fullmatch(repository) or repository.split("/")[1] in {".", ".."}:
        raise SourceError("Repository outside the source allowlist")


def checked_commit_tree(raw: bytes, commit: str) -> str:
    if not atlas.valid_sha(commit):
        raise SourceError("Malformed pinned commit SHA")
    git_bytes = f"commit {len(raw)}\0".encode("ascii") + raw
    if hashlib.sha1(git_bytes, usedforsecurity=False).hexdigest() != commit:
        raise SourceError("Raw Git commit hash mismatch")
    first = raw.split(b"\n", 1)[0]
    if re.fullmatch(rb"tree [a-f0-9]{40}", first) is None:
        raise SourceError("Git commit has no canonical root tree")
    return first[5:].decode("ascii")


def read_commit_tree(repository: str, commit: str) -> str:
    checked_repository(repository)
    if not atlas.valid_sha(commit):
        raise SourceError("Malformed pinned commit SHA")
    with tempfile.TemporaryDirectory(prefix="verify-git-commit-") as directory:
        git = ["git", "-C", directory]
        bounded_command([*git, "init", "--quiet", "--bare", "--object-format=sha1"], 10)
        bounded_command([*git, "remote", "add", "origin", f"https://github.com/{repository}.git"], 10)
        bounded_command([*git, "config", "remote.origin.promisor", "true"], 10)
        bounded_command([*git, "-c", "protocol.version=2", "-c", "credential.helper=",
                         "-c", "credential.helper=!gh auth git-credential", "fetch", "--quiet",
                         "--depth=1", "--filter=tree:0", "--no-tags", "origin", commit], 45)
        return checked_commit_tree(bounded_command([*git, "cat-file", "commit", commit], 10), commit)


def verify_pins(data: dict, report: dict) -> None:
    require_owner()
    pins = {}
    report["raw_commits_verified"] = []
    revisions = {(p["repository"], p["commit"]) for p in data["projects"]}
    for repo, commit in sorted(revisions):
        tree = read_commit_tree(repo, commit)
        pins[repo, commit] = tree
        report["raw_commits_verified"].append({"repository": repo, "commit": commit, "tree": tree})

    def fetch(repository: str, route: str) -> dict:
        checked_repository(repository)
        if not route.startswith(("git/commits/", "git/trees/", "contents/")):
            raise SourceError("Unexpected GitHub source route")
        report["source_requests"] += 1
        record = gh_object(f"repos/{repository}/{route}")
        if route.startswith("git/commits/"):
            commit = route.removeprefix("git/commits/")
            tree = record.get("tree")
            if not isinstance(tree, dict) or tree.get("sha") != pins.get((repository, commit)):
                raise SourceError("GitHub root differs from the verified Git commit")
        return record

    atlas.verify_remote(data, fetch)
    require_owner()
    report["blobs_verified"] = len(atlas.expected_blobs(data))


def verify_revision(ref: str, report: dict) -> None:
    raw = release.git_bytes("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
    commit = raw.decode("ascii").strip()
    if not atlas.valid_sha(commit):
        raise SourceError("Expected a SHA-1 repository revision")
    report["commit"] = commit
    report["tree"] = release.git_bytes("rev-parse", "--verify", f"{commit}^{{tree}}").decode("ascii").strip()
    with tempfile.TemporaryDirectory(prefix="verify-sources-tree-") as directory:
        checkout = Path(directory)
        release.extract_commit(commit, checkout)
        for module in ("verify_sources.py", "verify_release.py", "render_research_atlas.py"):
            if (checkout / "tools" / module).read_bytes() != Path(__file__).with_name(module).read_bytes():
                raise SourceError(f"Verifier module differs from the selected revision: {module}")
        data = atlas.load_manifest(checkout / "research/atlas.json")
    report["atlas_sha256"] = atlas.fingerprint(data)
    verify_pins(data, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ref", nargs="?", default="HEAD")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = {
        "schema": "neuron7x.source-verification.v1", "status": "FAIL", "commit": None, "tree": None,
        "atlas_sha256": None, "raw_commits_verified": [], "source_requests": 0, "blobs_verified": 0,
    }
    try:
        verify_revision(args.ref, report)
        report["status"] = "PASS"
    except (SourceError, release.VerificationError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"VERIFY_SOURCES_FAILED: {error}", file=sys.stderr)
    if args.report is not None:
        try:
            release.write_report(args.report, report)
        except OSError as error:
            print(f"VERIFY_SOURCES_FAILED: cannot write report: {error}", file=sys.stderr)
            return 1
    if report["status"] == "PASS":
        print("SOURCE_VERIFICATION_PASS")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
