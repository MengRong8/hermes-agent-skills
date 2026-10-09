#!/usr/bin/env python3
"""
code-author selftest harness.

Usage:
    python selftest.py '{
        "code": "def merge_intervals(intervals): ...",
        "constraints": {"entry_function": "merge_intervals", "max_loc": 500,
                        "imports_forbidden": ["os","sys"]},
        "sample_inputs": [
            {"input": [[[1,3],[2,4]]], "expected": [[1,4]]},
            {"input": [[]],            "expected": []}
        ]
    }'

Prints a single fenced JSON block:
    {"passed": int, "failed": int, "errors": [str],
     "sloc": int, "loc_violation": bool,
     "import_violations": [str]}

Deterministic. No LLM, no network. Uses `radon raw` for SLOC.
"""

from __future__ import annotations

import ast
import json
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

# Grader runs each hidden test with a 5s timeout (spec §2.3). Self-test uses a
# tighter budget so a borderline-slow algorithm is caught locally before submission.
SAMPLE_TIME_LIMIT_SEC = 2.0


class _Timeout(Exception):
    pass


@contextmanager
def _time_limit(seconds: float):
    """SIGALRM-based timeout. POSIX only; on Windows this is a no-op (no hard kill),
    but elapsed_sec is still measured via time.perf_counter() either way."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _handler(signum, frame):
        raise _Timeout(f"exceeded {seconds}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _emit(obj: dict) -> int:
    sys.stdout.write("```json\n")
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.stdout.write("\n```\n")
    return 0


def compute_sloc(code: str) -> int:
    """以 `radon raw <file> --json` 計算 SLOC(規格書 §2.3)。Fallback: 簡單非空非註解行數。"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = Path(f.name)
    try:
        try:
            proc = subprocess.run(
                ["radon", "raw", str(path), "--json"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout)
                # radon returns {filepath: {sloc: int, ...}}
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, dict) and "sloc" in v:
                            return int(v["sloc"])
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        # fallback
        count = 0
        for line in code.splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                count += 1
        return count
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def find_import_violations(code: str, forbidden: list[str]) -> list[str]:
    """以 AST 找 import,比對禁用清單。"""
    if not forbidden:
        return []
    forbidden_set = {f.strip() for f in forbidden if f.strip()}
    found: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["<syntax error — cannot static-check imports>"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden_set:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in forbidden_set:
                    found.append(node.module)
    return sorted(set(found))


def _timeout_msg(args, elapsed: float) -> str:
    return (
        f"timeout: input {args!r} took {elapsed:.2f}s, over the {SAMPLE_TIME_LIMIT_SEC}s "
        f"self-test budget - likely an algorithmic complexity issue (e.g. O(n^2)/O(n^3) "
        f"where O(n) or O(n log n) suffices); the grader uses a 5s/test limit and gives "
        f"0 credit for a timed-out test even if the logic is otherwise correct"
    )


def run_sample(code: str, entry: str, sample: dict) -> tuple[bool, str, float]:
    """Returns (ok, error_message, elapsed_sec)."""
    ns: dict = {}
    try:
        exec(compile(code, "<candidate>", "exec"), ns)
    except Exception as e:
        return False, f"compile/exec error: {e!r}", 0.0
    fn = ns.get(entry)
    if not callable(fn):
        return False, f"entry function {entry!r} not defined", 0.0
    args = sample.get("input", [])
    expected = sample.get("expected")
    start = time.perf_counter()
    try:
        with _time_limit(SAMPLE_TIME_LIMIT_SEC):
            got = fn(*args) if isinstance(args, list) else fn(args)
    except _Timeout:
        elapsed = time.perf_counter() - start
        return False, _timeout_msg(args, elapsed), elapsed
    except Exception as e:
        elapsed = time.perf_counter() - start
        return False, f"runtime error on input {args!r}: {e!r}", elapsed
    elapsed = time.perf_counter() - start
    # SIGALRM is POSIX-only (see _time_limit) — on platforms without it (e.g. Windows,
    # used for local dev in this project) the call above was never hard-killed, so a
    # slow-but-not-hanging algorithm would otherwise slip through as a silent "pass".
    # Catch that here too, so the same complexity bug is caught on every platform.
    if elapsed > SAMPLE_TIME_LIMIT_SEC:
        return False, _timeout_msg(args, elapsed), elapsed
    if got != expected:
        return False, f"mismatch on {args!r}: got {got!r}, expected {expected!r}", elapsed
    return True, "", elapsed


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _emit({"passed": 0, "failed": 0, "errors": ["usage: selftest.py '<json>'"],
                      "sloc": 0, "loc_violation": False, "import_violations": []})
    try:
        payload = json.loads(argv[1])
    except json.JSONDecodeError as e:
        return _emit({"passed": 0, "failed": 0, "errors": [f"argv JSON invalid: {e}"],
                      "sloc": 0, "loc_violation": False, "import_violations": []})

    code = str(payload.get("code", ""))
    constraints = payload.get("constraints", {}) or {}
    samples = payload.get("sample_inputs", []) or []

    sloc = compute_sloc(code)
    max_loc = int(constraints.get("max_loc", 500))
    loc_violation = sloc > max_loc
    import_violations = find_import_violations(code, constraints.get("imports_forbidden", []))

    entry = str(constraints.get("entry_function", ""))
    passed = 0
    failed = 0
    errors: list[str] = []
    max_elapsed_sec = 0.0
    if entry and samples:
        for s in samples:
            ok, err, elapsed = run_sample(code, entry, s)
            max_elapsed_sec = max(max_elapsed_sec, elapsed)
            if ok:
                passed += 1
            else:
                failed += 1
                errors.append(err)
    elif not entry:
        errors.append("constraints.entry_function not provided")

    # Even a *passing* sample that runs surprisingly slowly on a tiny input is a
    # red flag for hidden tests with larger N (grader: 5s/test, spec §2.3).
    slow_warning = 0 < max_elapsed_sec < SAMPLE_TIME_LIMIT_SEC and max_elapsed_sec > 0.5

    return _emit({
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "sloc": sloc,
        "loc_violation": loc_violation,
        "import_violations": import_violations,
        "max_elapsed_sec": round(max_elapsed_sec, 4),
        "slow_warning": slow_warning,
    })


if __name__ == "__main__":
    sys.exit(main(sys.argv))
