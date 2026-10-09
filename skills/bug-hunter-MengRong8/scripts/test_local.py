#!/usr/bin/env python3
"""
bug-hunter 本地 harness 測試 — 不需 Hermes。

用 reference_tasks 的 test_cases 當探針：
  - clean_code   → analyze 的 test_cases 探針應全部 ok（0 crash）
  - buggy_code   → analyze 應有 ≥1 crash 或 suspicious_lines
  - contract     → run.py 應輸出合法 JSON

Usage:
    python skills/bug-hunter-MengRong8/scripts/test_local.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REF_TASKS = REPO_ROOT / "dev_set" / "pairwise" / "reference_tasks"
ANALYZE = Path(__file__).parent / "analyze.py"
RUN = Path(__file__).parent / "run.py"


def run_analyze(code: str, entry: str, edge_inputs: list) -> dict:
    payload = {"code": code, "entry_function": entry, "edge_inputs": edge_inputs}
    proc = subprocess.run(
        [sys.executable, str(ANALYZE), json.dumps(payload)],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = proc.stdout
    lines = out.splitlines()
    in_block, body_lines = False, []
    for l in lines:
        if l.strip() == "```json":
            in_block = True; continue
        if l.strip() == "```" and in_block:
            break
        if in_block:
            body_lines.append(l)
    return json.loads("\n".join(body_lines)) if body_lines else {}


def run_contract(task_id: str, verdict: str, bugs: list) -> dict:
    payload = {"task_id": task_id, "verdict": verdict, "bugs": bugs, "confidence": 0.8}
    proc = subprocess.run(
        [sys.executable, str(RUN), json.dumps(payload)],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = proc.stdout
    lines = out.splitlines()
    in_block, body_lines = False, []
    for l in lines:
        if l.strip() == "```json":
            in_block = True; continue
        if l.strip() == "```" and in_block:
            break
        if in_block:
            body_lines.append(l)
    return json.loads("\n".join(body_lines)) if body_lines else {}


def get_entry(code: str) -> str:
    for line in code.splitlines():
        s = line.strip()
        if s.startswith("def "):
            return s[4:].split("(")[0].strip()
    return "unknown"


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
        entry = task.get("constraints", {}).get("entry_function", "")
        test_cases = task.get("test_cases", [])
        clean_code = task.get("clean_code", "")
        buggy_code = task.get("buggy_code", "")

        # edge_inputs 用 task 的 test_cases（型別正確）
        edge_inputs = [{"input": tc["input"], "label": str(tc.get("expected", ""))} for tc in test_cases]

        # --- clean_code：所有 test_cases 探針應 ok ---
        ar_clean = run_analyze(clean_code, entry or get_entry(clean_code), edge_inputs)
        clean_crashes = sum(1 for p in ar_clean.get("probes", []) if p["outcome"] == "crash")
        clean_ok = clean_crashes == 0

        # --- buggy_code：應有 crash 或 suspicious_lines ---
        ar_buggy = run_analyze(buggy_code, entry or get_entry(buggy_code), edge_inputs)
        buggy_crashes = sum(1 for p in ar_buggy.get("probes", []) if p["outcome"] == "crash")
        buggy_suspicious = len(ar_buggy.get("suspicious_lines", []))
        buggy_detected = buggy_crashes > 0 or buggy_suspicious > 0

        # --- contract output ---
        bug_entry: list = []
        if ar_buggy.get("suspicious_lines"):
            sl = ar_buggy["suspicious_lines"][0]
            bug_entry = [{
                "line_start": sl, "line_end": sl,
                "severity": "medium", "type": "edge_case",
                "description": f"crash at line {sl}",
                "suggested_fix": "add input guard",
            }]
        contract = run_contract(tid, "buggy" if bug_entry else "clean", bug_entry)
        contract_ok = contract.get("task_id") == tid and contract.get("verdict") in ("buggy", "clean")

        ok = clean_ok and contract_ok
        mark = "OK " if ok else "FAIL"
        print(
            f"[{mark}] {tid}  "
            f"clean_crashes={clean_crashes}  "
            f"buggy_signal=crashes:{buggy_crashes}/susp:{buggy_suspicious}  "
            f"contract={'ok' if contract_ok else 'FAIL'}"
        )
        if not clean_ok:
            for p in ar_clean.get("probes", []):
                if p["outcome"] == "crash":
                    print(f"       clean crash on [{p['label']}]: {p['error']}")
        if not buggy_detected:
            print(f"       WARN: buggy code left no signal — dynamic probing won't help LLM here (static review needed)")

        if ok:
            passed_total += 1
        else:
            failed_total += 1

    total = passed_total + failed_total
    print(f"\n{passed_total}/{total} passed")
    return 0 if failed_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
