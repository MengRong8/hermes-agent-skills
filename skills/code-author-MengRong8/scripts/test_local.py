#!/usr/bin/env python3
"""
code-author 本地 harness 測試 — 不需 Hermes。

用 reference_tasks 的 clean_code 驗 selftest.py 能否通過，
確認 selftest.py import check + SLOC 計算 + test case execution 都正確。

Usage:
    python skills/code-author-MengRong8/scripts/test_local.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REF_TASKS = REPO_ROOT / "dev_set" / "pairwise" / "reference_tasks"
SELFTEST = Path(__file__).parent / "selftest.py"
RUN = Path(__file__).parent / "run.py"


def run_selftest(code: str, constraints: dict, test_cases: list) -> dict:
    payload = {
        "code": code,
        "constraints": constraints,
        "sample_inputs": test_cases,
    }
    proc = subprocess.run(
        [sys.executable, str(SELFTEST), json.dumps(payload)],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = proc.stdout
    # extract JSON from fenced block
    lines = out.splitlines()
    in_block = False
    body_lines = []
    for l in lines:
        if l.strip() == "```json":
            in_block = True
            continue
        if l.strip() == "```" and in_block:
            break
        if in_block:
            body_lines.append(l)
    return json.loads("\n".join(body_lines)) if body_lines else {}


def run_contract(task_id: str, code: str, st: dict) -> dict:
    payload = {
        "task_id": task_id,
        "code": code,
        "loc": st.get("sloc", 0),
        "self_test_results": {"passed": st.get("passed", 0), "failed": st.get("failed", 0)},
        "rationale": "local test",
        "confidence": 0.9,
    }
    proc = subprocess.run(
        [sys.executable, str(RUN), json.dumps(payload)],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = proc.stdout
    lines = out.splitlines()
    in_block = False
    body_lines = []
    for l in lines:
        if l.strip() == "```json":
            in_block = True
            continue
        if l.strip() == "```" and in_block:
            break
        if in_block:
            body_lines.append(l)
    return json.loads("\n".join(body_lines)) if body_lines else {}


def main() -> int:
    tasks = sorted(REF_TASKS.glob("task_pair_*.json"))
    if not tasks:
        print(f"No reference tasks found under {REF_TASKS}")
        return 1

    passed_total = 0
    failed_total = 0

    for tp in tasks:
        task = json.loads(tp.read_text(encoding="utf-8"))
        tid = task["task_id"]
        constraints = task.get("constraints", {})
        test_cases = task.get("test_cases", [])
        clean_code = task.get("clean_code", "")

        # 1. selftest with clean_code + test_cases
        st = run_selftest(clean_code, constraints, test_cases)
        all_pass = st.get("passed", 0) == len(test_cases) and st.get("failed", 0) == 0
        loc_ok = not st.get("loc_violation", False)
        imp_ok = not st.get("import_violations", [])

        # 2. run.py contract output
        contract = run_contract(tid, clean_code, st)
        contract_ok = contract.get("task_id") == tid and bool(contract.get("code", "").strip())

        ok = all_pass and loc_ok and imp_ok and contract_ok
        mark = "OK " if ok else "FAIL"
        detail = (
            f"tests={st.get('passed',0)}/{len(test_cases)} "
            f"sloc={st.get('sloc','?')} "
            f"loc_viol={st.get('loc_violation',False)} "
            f"imp_viol={st.get('import_violations',[])} "
            f"contract={'ok' if contract_ok else 'FAIL'}"
        )
        print(f"[{mark}] {tid}  {detail}")
        if not ok:
            if st.get("errors"):
                for e in st["errors"][:3]:
                    print(f"       error: {e}")
            failed_total += 1
        else:
            passed_total += 1

    total = passed_total + failed_total
    print(f"\n{passed_total}/{total} passed")
    return 0 if failed_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
