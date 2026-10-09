#!/usr/bin/env python3
"""
equiv_checker.py — Execute two Python functions on a shared test suite and report differences.

Usage:
    python skills/open-equiv-check-MengRong8/scripts/equiv_checker.py '<json_payload>'

Input JSON:
    {
        "func_a_code": "def foo(x):\\n    return x+1",
        "func_b_code": "def foo(x):\\n    return x+2",
        "entry_a": "foo",
        "entry_b": "foo",
        "test_cases": [
            {"input": [1], "label": "positive"},
            {"input": [0], "label": "zero"}
        ]
    }

Output JSON:
    {
        "all_equal": false,
        "first_difference": {"input": [1], "label": "positive", "output_a": 2, "output_b": 3},
        "results": [...],
        "summary": "1/2 test cases differ"
    }
"""
import json
import sys


def _run_fn(code: str, entry: str, args: list):
    """Execute `entry` defined in `code` with positional `args`. Returns (result, error_str)."""
    ns = {}
    try:
        exec(compile(code, "<func>", "exec"), ns)
    except Exception as exc:
        return None, f"CompileError: {exc}"
    fn = ns.get(entry)
    if fn is None:
        return None, f"EntryNotFound: '{entry}' not defined in code"
    try:
        return fn(*args), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: equiv_checker.py '<json_payload>'"}))
        sys.exit(1)

    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid JSON: {exc}"}))
        sys.exit(1)

    code_a    = payload.get("func_a_code", "")
    code_b    = payload.get("func_b_code", "")
    entry_a   = payload.get("entry_a", "")
    entry_b   = payload.get("entry_b", "")
    test_cases = payload.get("test_cases", [])

    results: list[dict] = []
    first_diff = None

    for tc in test_cases:
        args  = tc.get("input", [])
        label = tc.get("label", "")

        out_a, err_a = _run_fn(code_a, entry_a, args)
        out_b, err_b = _run_fn(code_b, entry_b, args)

        if err_a is None and err_b is None:
            equal = (out_a == out_b)
        elif err_a is not None and err_b is not None:
            # both crashed — equal only if same exception type
            equal = err_a.split(":")[0] == err_b.split(":")[0]
        else:
            equal = False  # one crashed, one did not

        row = {
            "input": args, "label": label,
            "output_a": out_a, "output_b": out_b,
            "error_a": err_a, "error_b": err_b,
            "equal": equal,
        }
        results.append(row)
        if not equal and first_diff is None:
            first_diff = row

    num_diff  = sum(1 for r in results if not r["equal"])
    all_equal = (num_diff == 0)

    print(json.dumps({
        "all_equal": all_equal,
        "first_difference": first_diff,
        "results": results,
        "summary": f"{num_diff}/{len(test_cases)} test cases differ",
    }, ensure_ascii=False, default=str))
    sys.exit(0 if all_equal else 1)


if __name__ == "__main__":
    main()
