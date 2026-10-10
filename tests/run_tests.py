#!/usr/bin/env python3
"""Compile and run @lam/vulture/tus-plugin tests in an isolated extlibs tree."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


LIB_ROOT = Path(__file__).resolve().parents[1]
CORE_LIB_ROOT = LIB_ROOT.parent / "lam-vulture"
COMPILER = "lamc"
MIN_COMPILER_VERSION = (1, 18, 0)
PACKAGE_PATH = Path("@lam") / "vulture" / "tus-plugin"
CORE_PACKAGE_PATH = Path("@lam") / "vulture"
VERSION_PATTERN = re.compile(r"(?:lamc\s+)?v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?")


def _run(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _check_compiler() -> bool:
    try:
        proc = _run([COMPILER, "version"], cwd=LIB_ROOT, timeout=10)
    except FileNotFoundError:
        print(f"Error: {COMPILER} is not installed or is not on PATH.", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print(f"Error: {COMPILER} version check timed out.", file=sys.stderr)
        return False
    except OSError as exc:
        print(f"Error: unable to run {COMPILER}: {exc}", file=sys.stderr)
        return False

    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit status {proc.returncode}"
        print(f"Error: unable to check {COMPILER} version: {detail}", file=sys.stderr)
        return False

    version_text = proc.stdout.strip()
    match = VERSION_PATTERN.fullmatch(version_text)
    if not match:
        print(f"Error: {COMPILER} returned an invalid version: {version_text!r}.", file=sys.stderr)
        return False

    version = tuple(int(part) for part in match.groups())
    if version < MIN_COMPILER_VERSION:
        required = ".".join(str(part) for part in MIN_COMPILER_VERSION)
        print(
            f"Error: {COMPILER} {version_text} is incompatible; version >= {required} is required.",
            file=sys.stderr,
        )
        return False
    return True


def _expectations(source: str) -> list[str]:
    return [
        match.group(1).strip()
        for line in source.splitlines()
        if (match := re.match(r"^\s*#\s*expect:\s*(.*)$", line))
    ]


def _copy_package(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            "build",
            "extlibs",
            "*.lamc-cache",
            "__pycache__",
            "*.pyc",
        ),
    )


def _stage_packages(extlibs: Path) -> None:
    _copy_package(CORE_LIB_ROOT, extlibs / CORE_PACKAGE_PATH)
    _copy_package(LIB_ROOT, extlibs / PACKAGE_PATH)


def _process_failure(label: str, proc: subprocess.CompletedProcess[str]) -> str:
    details = [f"{label} ({proc.returncode})"]
    if proc.stdout.strip():
        details.append("stdout:\n" + proc.stdout.rstrip())
    if proc.stderr.strip():
        details.append("stderr:\n" + proc.stderr.rstrip())
    return "\n".join(details)


def _run_case(path: Path, *, race: bool) -> tuple[bool, str]:
    expected = _expectations(path.read_text(encoding="utf-8"))
    if not expected:
        return False, "TEST ERROR: no '# expect:' lines found"

    with tempfile.TemporaryDirectory(prefix="lam_vulture_tus_test_") as tmp:
        root = Path(tmp)
        extlibs = root / "extlibs"
        _stage_packages(extlibs)
        binary = root / "test_binary"
        command = [
            COMPILER,
            str(path),
            "--extlibs",
            str(extlibs),
            "--no-cache",
            "-o",
            str(binary),
        ]
        if race:
            command.append("--go-race")

        try:
            compile_proc = _run(command, cwd=root, timeout=240)
        except subprocess.TimeoutExpired:
            return False, "COMPILE FAIL: timed out after 240 seconds"
        except OSError as exc:
            return False, f"COMPILE FAIL: unable to run {COMPILER}: {exc}"
        if compile_proc.returncode != 0:
            return False, _process_failure("COMPILE FAIL", compile_proc)

        try:
            run_proc = _run([str(binary)], cwd=root, timeout=60)
        except subprocess.TimeoutExpired:
            return False, "RUN FAIL: timed out after 60 seconds"
        except OSError as exc:
            return False, f"RUN FAIL: unable to execute test binary: {exc}"
        if run_proc.returncode != 0:
            return False, _process_failure("RUN FAIL", run_proc)

        actual = run_proc.stdout.rstrip("\n")
        expected_text = "\n".join(expected)
        if actual != expected_text:
            return (
                False,
                "OUTPUT MISMATCH:\n"
                f"  expected: {expected_text!r}\n"
                f"  actual:   {actual!r}"
                + (f"\n  stderr:   {run_proc.stderr.rstrip()!r}" if run_proc.stderr else ""),
            )
        return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="@lam/vulture/tus-plugin package tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="show full failure details")
    parser.add_argument("--race", action="store_true", help="build tests with Go's race detector")
    args = parser.parse_args()

    if not _check_compiler():
        return 1
    if not (CORE_LIB_ROOT / "lamlib.toml").is_file():
        print(
            f"Error: local @lam/vulture checkout is required at {CORE_LIB_ROOT}",
            file=sys.stderr,
        )
        return 1

    cases = sorted((LIB_ROOT / "tests").glob("test_*.lam"))
    if not cases:
        print("Error: no @lam/vulture/tus-plugin test cases found.", file=sys.stderr)
        return 1

    failures: list[tuple[Path, str]] = []
    print(f"Running {len(cases)} @lam/vulture/tus-plugin test(s)...\n")
    for case in cases:
        ok, message = _run_case(case, race=args.race)
        relative = case.relative_to(LIB_ROOT)
        print(f"  {'PASS' if ok else 'FAIL'}  {relative}")
        if not ok:
            failures.append((relative, message))
            if args.verbose:
                for line in message.splitlines():
                    print(f"        {line}")

    passed = len(cases) - len(failures)
    print(
        f"\n@lam/vulture/tus-plugin results: "
        f"{passed} passed, {len(failures)} failed, {len(cases)} total"
    )
    if failures and not args.verbose:
        print("Re-run with --verbose for failure details.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
