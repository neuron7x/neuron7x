#!/usr/bin/env python3
"""Verify an exact Git commit locally, with no installs or remote checks."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 120
INJECTION_ENV = {
    "NODE_OPTIONS", "NODE_PATH", "NODE_TEST_CONTEXT", "NODE_V8_COVERAGE",
    "PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE",
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_NAMESPACE", "GIT_COMMON_DIR",
}
VERIFY_ENV = {key: value for key, value in os.environ.items() if key not in INJECTION_ENV}
VERIFY_ENV["GIT_NO_REPLACE_OBJECTS"] = "1"


class VerificationError(Exception):
    pass


def execute(command: list[str], directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=directory, capture_output=True, encoding="utf-8",
        errors="replace", timeout=TIMEOUT, check=False, env=VERIFY_ENV,
    )


def git_bytes(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, env=VERIFY_ENV,
        timeout=TIMEOUT, check=True,
    ).stdout


def tree_index(commit: str) -> dict[str, tuple[str, str]]:
    records = git_bytes("ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0")
    index = {}
    for record in records[:-1]:
        metadata, path = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        name = os.fsdecode(path)
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise VerificationError(f"Unsupported Git tree entry: {name}")
        if name in index or not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", oid):
            raise VerificationError(f"Invalid Git tree entry: {name}")
        index[name] = (mode, oid)
    return index


def extract_commit(commit: str, destination: Path) -> int:
    index = tree_index(commit)
    pending = dict(index)
    paths = {str(p) for name in index for p in PurePosixPath(name).parents if str(p) != "."}
    raw = git_bytes("archive", "--format=tar", commit)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive:
            target = destination / member.name
            if not target.resolve().is_relative_to(destination):
                raise VerificationError(f"Archive path escapes destination: {member.name}")
            if member.isdir() and member.name in paths:
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isreg() or member.name not in pending:
                raise VerificationError(f"Unexpected or duplicate archive entry: {member.name}")
            mode, oid = pending.pop(member.name)
            executable = mode == "100755"
            if bool(member.mode & 0o111) != executable:
                raise VerificationError(f"Archive mode differs from Git tree: {member.name}")
            algorithm = "sha1" if len(oid) == 40 else "sha256"
            digest = hashlib.new(algorithm, usedforsecurity=False)
            digest.update(f"blob {member.size}\0".encode("ascii"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("xb") as output:
                while chunk := source.read(65536):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != oid:
                raise VerificationError(f"Archive bytes differ from Git tree: {member.name}")
            target.chmod(0o755 if executable else 0o644)

    if pending:
        raise VerificationError("Archive omits Git tree paths: " + ", ".join(sorted(pending)))
    return len(index)


def require_committed_verifier(checkout: Path) -> str:
    archived = checkout / "tools/verify_release.py"
    if not archived.is_file() or archived.read_bytes() != Path(__file__).resolve().read_bytes():
        raise VerificationError("Verifier differs from the selected Git revision")
    return hashlib.sha256(archived.read_bytes()).hexdigest()


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

    anchor_test = "external receipt digest rejects a valid replacement case and receipt together"

    def reject_detached_anchor() -> None:
        command = [*node, f"--test-name-pattern=^{anchor_test}$", "tests/inference_receipt.test.mjs"]
        require("Anchored verification rejects a substituted case and receipt", command, root, 1, lambda result: (
            re.search(rf"^not ok [0-9]+ - {anchor_test}$", result.stdout, re.MULTILINE) is not None
            and "ERR_ASSERTION" in result.stdout
            and "Missing expected exception" in result.stdout
        ))

    mutate(root, "inference/receipt.mjs",
           lambda source: source.replace(b"receipt.receipt_sha256 !== expectedDigest", b"false"),
           reject_detached_anchor)

    forecast_test = "forecast scores agree with executable terminal outcomes and total action uses"

    def reject_inflated_forecast() -> None:
        command = [*node, f"--test-name-pattern=^{forecast_test}$", "tests/inference_receipt.test.mjs"]
        require("Receipt detects inflated selection forecasts", command, root, 1, lambda result: (
            re.search(rf"^not ok [0-9]+ - {forecast_test}$", result.stdout, re.MULTILINE) is not None
            and "INVALID_INFERENCE_FORECAST" in result.stdout
        ))

    mutate(root, "inference/kernel.mjs",
           lambda source: source.replace(b"selected_models:plan.selections", b"selected_models:plan.selections+1"),
           reject_inflated_forecast)

    def reject_symlink_admission() -> None:
        require("Git tree verifier rejects a symbolic link", [*python, "-m", "unittest", "discover", "-s", "tests"],
                root, 1, lambda result: (
                    "FAIL: test_commit_tree_requires_regular_leaf_before_content_is_requested" in result.stderr
                    and "label='symlink'" in result.stderr
                    and "ValueError not raised" in result.stderr
                ))

    mutate(root, "tools/render_research_atlas.py",
           lambda source: source.replace(b'{"100644", "100755"}', b'{"100644", "100755", "120000"}'),
           reject_symlink_admission)

    planner_loop = b"for (const first of interventions) {"
    forecast_controls = [
        ("Receipt rejects a coherent coverage loss",
         "forecast optimality maximizes selections for both policies",
         planner_loop + b' if (horizon === 2 && models.length === 5 && first !== "C") continue;'),
        ("Receipt rejects coherent excess action cost",
         "forecast optimality minimizes costs and resolves root ties",
         planner_loop + b' if (horizon === 2 && models.length === 4 && first !== "A") continue;'),
        ("Receipt rejects a coherent wrong root tie",
         "forecast optimality minimizes costs and resolves root ties",
         planner_loop + b' if (horizon === 2 && models.length === 4 && first !== "C") continue;'),
        ("Receipt rejects a coherent wrong branch tie",
         "forecast optimality checks lexical ties inside every branch",
         b"for (const first of (horizon === 1 ? [...interventions].reverse() : interventions)) {"),
    ]

    for name, test_name, altered_loop in forecast_controls:
        def reject_suboptimal_forecast() -> None:
            command = [*node, f"--test-name-pattern=^{test_name}$", "tests/inference_receipt.test.mjs"]
            require(name, command, root, 1, lambda result: (
                re.search(rf"^not ok [0-9]+ - {test_name}$", result.stdout, re.MULTILINE) is not None
                and "SUBOPTIMAL_INFERENCE_FORECAST" in result.stdout
            ))

        mutate(root, "inference/two_step_policy.mjs",
               lambda source: source.replace(planner_loop, altered_loop, 1), reject_suboptimal_forecast)

    successor_test = "dual anchors distinguish two individually valid successors of the same parent"

    def reject_detached_successor() -> None:
        command = [*node, f"--test-name-pattern=^{successor_test}$", "tests/inference_receipt.test.mjs"]
        require("Dual anchors reject a valid sibling substitution", command, root, 1, lambda result: (
            re.search(rf"^not ok [0-9]+ - {successor_test}$", result.stdout, re.MULTILINE) is not None
            and "Missing expected exception" in result.stdout and "ERR_ASSERTION" in result.stdout
        ))

    mutate(root, "inference/receipt.mjs",
           lambda source: source.replace(b"if (nextDigest !== undefined) requireAnchor(expected, nextDigest);", b""),
           reject_detached_successor)

    proof_controls = [
        ("Git tree hash rejects an unrelated altered entry", "tools/render_research_atlas.py",
         b'if hashlib.sha1(header + payload, usedforsecurity=False).hexdigest() != expected_sha:',
         b"if False:", "test_research_atlas.py",
         "test_tree_hash_matches_git_sorting_and_detects_unrelated_entry_changes", "ValueError not raised"),
        ("Archive index rejects hidden tracked files", "tools/verify_release.py",
         b"if pending:", b"if False:", "test_verify_release.py",
         "test_archive_rejects_tracked_file_hidden_by_local_attributes", "VerificationError not raised"),
        ("Release entrypoint rejects a stale verifier", "tools/verify_release.py",
         b"if not archived.is_file() or archived.read_bytes() != Path(__file__).resolve().read_bytes():",
         b"if not archived.is_file():", "test_verify_release.py",
         "test_runner_must_match_the_revision", "VerificationError not raised"),
    ]

    for name, source_path, original, altered, suite, case, diagnostic in proof_controls:
        def reject_failed_proof() -> None:
            command = [*python, "-m", "unittest", "discover", "-s", "tests", "-p", suite]
            require(name, command, root, 1, lambda result: (
                f"FAIL: {case}" in result.stderr and diagnostic in result.stderr
            ))

        mutate(root, source_path, lambda source: source.replace(original, altered, 1), reject_failed_proof)


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
        tree = execute(["git", "rev-parse", "--verify", f"{commit}^{{tree}}"], ROOT)
        if tree.returncode != 0 or not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", tree.stdout.strip()):
            raise VerificationError(f"Cannot resolve Git tree for {commit}")
        print(f"COMMIT {commit}", flush=True)
        print(f"TREE {tree.stdout.strip()}", flush=True)
        with tempfile.TemporaryDirectory(prefix="verify-release-") as temporary:
            checkout = Path(temporary).resolve()
            count = extract_commit(commit, checkout)
            print(f"TRACKED_BLOBS_VERIFIED {count}", flush=True)
            verifier = require_committed_verifier(checkout)
            print(f"VERIFIER_SHA256 {verifier}", flush=True)
            verify(checkout)
    except (VerificationError, OSError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"VERIFY_RELEASE_FAILED: {error}", file=sys.stderr)
        return 1
    print("RELEASE_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
