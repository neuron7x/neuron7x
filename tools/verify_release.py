#!/usr/bin/env python3
"""Verify an exact Git commit locally, with no installs or remote checks."""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 120
INJECTION_ENV = {
    "NODE_OPTIONS", "NODE_PATH", "NODE_TEST_CONTEXT", "NODE_V8_COVERAGE",
    "PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE",
}
VERIFY_ENV = {key: value for key, value in os.environ.items() if key not in INJECTION_ENV}


class VerificationError(Exception):
    pass


def execute(command: list[str], directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=directory, capture_output=True, encoding="utf-8",
        errors="replace", timeout=TIMEOUT, check=False, env=VERIFY_ENV,
    )


def extract_commit(commit: str, destination: Path) -> None:
    result = subprocess.run(
        ["git", "archive", "--format=tar", commit], cwd=ROOT, capture_output=True,
        timeout=TIMEOUT, check=True,
    )
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive:
            target = destination / member.name
            if not target.resolve().is_relative_to(destination):
                raise VerificationError(f"Archive path escapes destination: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isreg():
                raise VerificationError(f"Archive contains a non-regular entry: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)


def require(
    name: str,
    command: list[str],
    directory: Path,
    status: int,
    predicate: Callable[[subprocess.CompletedProcess[str]], bool],
) -> None:
    print(f"RUN {name}", flush=True)
    result = execute(command, directory)
    if result.returncode != status or not predicate(result):
        details = "\n".join(part.strip() for part in (result.stderr, result.stdout) if part.strip())
        raise VerificationError(
            f"{name}: expected exit {status} and its diagnostic, got exit {result.returncode}"
            + (f"\n{details}" if details else "")
        )
    print(f"PASS {name} (exit {status})", flush=True)


def node_suite(result: subprocess.CompletedProcess[str]) -> bool:
    count = re.search(r"^# tests ([1-9][0-9]*)$", result.stdout, re.MULTILINE)
    return count is not None and f"# pass {count[1]}" in result.stdout.splitlines()


def python_suite(result: subprocess.CompletedProcess[str]) -> bool:
    return (
        re.search(r"^Ran [1-9][0-9]* tests? in ", result.stderr, re.MULTILINE) is not None
        and result.stderr.rstrip().endswith("\nOK")
    )


def mutate(
    root: Path,
    relative_path: str,
    change: Callable[[bytes], bytes],
    check: Callable[[], None],
) -> None:
    path = root / relative_path
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"Negative-control target is not a regular file: {relative_path}")
    original = path.read_bytes()
    altered = change(original)
    if altered == original:
        raise VerificationError(f"Negative control made no change: {relative_path}")
    path.write_bytes(altered)
    try:
        check()
    finally:
        path.write_bytes(original)


def grant_causal_authority(content: bytes) -> bytes:
    altered, count = re.subn(
        rb"(\bcausal_authority\s*:\s*)false\b", rb"\g<1>true", content
    )
    if count != 1:
        raise VerificationError("Expected exactly one causal-authority invariant to mutate")
    return altered


def verify(root: Path) -> None:
    node = ["node", "--test", "--test-reporter=tap"]
    python = [sys.executable, "-B"]
    traces = ["node", "tools/run_inference.mjs", "--check"]
    signal = ["node", "tools/render_epistemic_signal.mjs", "--check"]
    atlas = [*python, "tools/render_research_atlas.py", "--check"]
    require("Node test suite", node, root, 0, node_suite)
    require("Python test suite", [*python, "-m", "unittest", "discover", "-s", "tests"],
            root, 0, python_suite)
    require("CLI conformance", traces, root, 0, lambda result: re.fullmatch(
        r"INFERENCE_CONFORMANCE: ([6-9]|[1-9][0-9]+)/\1 snapshots match\n?",
        result.stdout,
    ) is not None and not result.stderr)
    require("Epistemic Signal renderer", signal, root, 0, lambda result: (
        result.stdout.strip() == "EPISTEMIC SIGNAL: CONSISTENT; no experiment claims"
        and not result.stderr
    ))
    require("Research Atlas renderer", atlas, root, 0, lambda result: (
        re.fullmatch(r"Consistent: [1-9][0-9]* atlas files; [1-9][0-9]* source-pinned projects\.\n?",
                     result.stdout) is not None
        and not result.stderr
    ))

    controls = [
        ("CLI rejects changed exact trace", "inference/results/adaptive_categorical.json",
         traces, "SNAPSHOT_MISMATCH adaptive_categorical"),
        ("Epistemic Signal rejects changed SVG", "assets/epistemic-signal-dark.svg",
         signal, "OUT OF DATE: assets/epistemic-signal-dark.svg"),
        ("Research Atlas rejects changed Markdown", "RESEARCH_ATLAS.md",
         atlas, "Generated files differ: RESEARCH_ATLAS.md"),
    ]
    for name, path, command, message in controls:
        def reject_artifact() -> None:
            require(name, command, root, 1,
                    lambda result: result.stderr.strip() == message and not result.stdout)

        mutate(root, path, lambda original: original + b"\n", reject_artifact)

    boundary_test = "intervention selects model conditionally but never grants causality"

    def reject_authority() -> None:
        command = [*node, f"--test-name-pattern=^{boundary_test}$", "tests/inference_gate.test.mjs"]
        require("Inference rejects granted causal authority", command, root, 1, lambda result: (
            re.search(rf"^not ok [0-9]+ - {boundary_test}$", result.stdout, re.MULTILINE) is not None
            and "ERR_ASSERTION" in result.stdout
            and "true !== false" in result.stdout
        ))

    mutate(root, "inference/kernel.mjs", grant_causal_authority, reject_authority)

    receipt_test = "a changed rival invalidates the receipt even if the exact verdict is unchanged"

    def reject_detached_declaration() -> None:
        command = [*node, f"--test-name-pattern=^{receipt_test}$", "tests/inference_receipt.test.mjs"]
        require("Receipt rejects detached declarations and evidence", command, root, 1, lambda result: (
            re.search(rf"^not ok [0-9]+ - {receipt_test}$", result.stdout, re.MULTILINE) is not None
            and "ERR_ASSERTION" in result.stdout
            and "Missing expected exception" in result.stdout
        ))

    mutate(root, "inference/receipt.mjs",
           lambda source: source.replace(b"declaration_sha256: digest(declaration(input))",
                                         b"declaration_sha256: digest({})"),
           reject_detached_declaration)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ref", nargs="?", default="HEAD", help="local Git commit or ref")
    args = parser.parse_args()
    try:
        resolved = execute(["git", "rev-parse", "--verify", "--end-of-options",
                            f"{args.ref}^{{commit}}"], ROOT)
        commit = resolved.stdout.strip()
        if resolved.returncode != 0 or not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", commit):
            raise VerificationError(f"Cannot resolve a local Git commit: {args.ref}")
        print(f"COMMIT {commit}", flush=True)
        with tempfile.TemporaryDirectory(prefix="verify-release-") as temporary:
            checkout = Path(temporary).resolve()
            extract_commit(commit, checkout)
            verify(checkout)
    except (VerificationError, OSError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"VERIFY_RELEASE_FAILED: {error}", file=sys.stderr)
        return 1
    print("RELEASE_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
