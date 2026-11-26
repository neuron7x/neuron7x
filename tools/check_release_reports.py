"""Check two independently produced release reports against one Git revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

from .verify_release import git_bytes

MAX_REPORT_BYTES = 65536
EXPECTED = {
    "check": frozenset({
        "CLI conformance",
        "Epistemic Signal renderer",
        "Node test suite",
        "Python test suite",
        "Research Atlas renderer",
    }),
    "negative-control": frozenset({
        "Anchored verification rejects a substituted case and receipt",
        "Archive index rejects hidden tracked files",
        "CLI rejects changed exact trace",
        "Dual anchors reject a valid sibling substitution",
        "Epistemic Signal rejects changed SVG",
        "Git tree hash rejects an unrelated altered entry",
        "Git tree verifier rejects a symbolic link",
        "Inference rejects granted causal authority",
        "Receipt detects inflated selection forecasts",
        "Independent reports reject coherent execution-order drift",
        "Receipt rejects a coherent coverage loss",
        "Receipt rejects a coherent wrong branch tie",
        "Receipt rejects a coherent wrong root tie",
        "Receipt rejects coherent excess action cost",
        "Receipt rejects detached declarations and evidence",
        "Release entrypoint rejects a stale verifier",
        "Research Atlas rejects changed Markdown",
        "Source verification rejects a modified raw commit",
    }),
}

FIELDS = {
    "schema", "status", "failed_stage", "commit", "tree", "tracked_blobs_verified",
    "verifier_sha256", "checks", "negative_controls",
}
ROW_FIELDS = {"name", "kind", "expected_exit", "actual_exit", "status"}
SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def load_report(path: Path) -> tuple[dict, bytes, tuple[int, int]]:
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Verification report is not a regular file")
        data = stream.read(MAX_REPORT_BYTES + 1)
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError("Oversized verification report")
    report = json.loads(data.decode("utf-8"))
    canonical = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if data != canonical or not isinstance(report, dict):
        raise ValueError("Noncanonical verification report")
    return report, data, (info.st_dev, info.st_ino)


def validate(report: dict, commit: str, tree: str, verifier_sha256: str, blobs: int) -> None:
    if (
        set(report) != FIELDS or report["schema"] != "neuron7x.release-verification.v1"
        or report["status"] != "PASS" or report["failed_stage"] is not None
        or report["commit"] != commit or report["tree"] != tree
        or report["verifier_sha256"] != verifier_sha256
        or type(report["tracked_blobs_verified"]) is not int or report["tracked_blobs_verified"] != blobs
        or not isinstance(report["checks"], list)
    ):
        raise ValueError("Verification report differs from the committed revision")

    seen = {kind: set() for kind in EXPECTED}
    for row in report["checks"]:
        if not isinstance(row, dict) or set(row) != ROW_FIELDS:
            raise ValueError("Invalid check entry")
        kind, name = row["kind"], row["name"]
        if (not isinstance(kind, str) or kind not in EXPECTED or not isinstance(name, str)
                or name not in EXPECTED[kind] or name in seen[kind]):
            raise ValueError("Unknown or repeated verification check")
        expected_exit = 0 if kind == "check" else 1
        codes = (row["expected_exit"], row["actual_exit"])
        if row["status"] != "PASS" or any(type(code) is not int or code != expected_exit for code in codes):
            raise ValueError("Unexpected check result")
        seen[kind].add(name)
    if seen != EXPECTED:
        raise ValueError("Missing required release checks")

    count = report["negative_controls"]
    if (not isinstance(count, dict) or set(count) != {"passed", "failed"}
            or any(type(number) is not int for number in count.values())
            or count != {"passed": len(seen["negative-control"]), "failed": 0}):
        raise ValueError("Incorrect negative-control counts")


def compare(first: Path, second: Path, identity: tuple[str, str, str, int]) -> str:
    left, left_bytes, left_file = load_report(first)
    right, right_bytes, right_file = load_report(second)
    if left_file == right_file:
        raise ValueError("Independent releases require two distinct report files")
    validate(left, *identity)
    validate(right, *identity)
    if left_bytes != right_bytes:
        raise ValueError("Independent release reports differ")
    return hashlib.sha256(left_bytes).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commit", help="full expected commit SHA")
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args()
    try:
        commit = args.commit
        if not SHA.fullmatch(commit) or git_bytes("rev-parse", "--verify", f"{commit}^{{commit}}").strip().decode() != commit:
            raise ValueError("Expected a full Git commit SHA")
        tree = git_bytes("rev-parse", "--verify", f"{commit}^{{tree}}").strip().decode()
        verifier = hashlib.sha256(git_bytes("show", f"{commit}:tools/verify_release.py")).hexdigest()
        count = git_bytes("ls-tree", "-rz", commit).count(b"\0")
        digest = compare(args.first, args.second, (commit, tree, verifier, count))
        print(f"REPEAT_VERIFICATION_PASS {digest}")
        return 0
    except (ValueError, RecursionError, OSError, subprocess.SubprocessError) as error:
        print(f"REPEAT_VERIFICATION_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
