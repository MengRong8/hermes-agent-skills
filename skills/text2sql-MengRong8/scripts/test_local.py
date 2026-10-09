#!/usr/bin/env python3
"""
本地快速測試腳本 — 不需要 Hermes，直接驗證 harness 正確性。

用法:
    # 測試所有 dev_set/basic 題目（只跑 harness，不跑 LLM）
    python skills/text2sql-MengRong8/scripts/test_local.py

    # 測試單一題，指定 gold_sql（模擬 LLM 給了正確答案）
    python skills/text2sql-MengRong8/scripts/test_local.py --task dev_set/basic/task_nl2sql_001.json

    # 測試一段自訂 SQL 對某題
    python skills/text2sql-MengRong8/scripts/test_local.py --task dev_set/basic/task_nl2sql_001.json --sql "SELECT name FROM Students"
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = Path(__file__).resolve().parent


def bag_equal(rows_a, rows_b) -> bool:
    def to_hashable(row):
        return tuple(row) if isinstance(row, (list, tuple)) else (row,)
    return Counter(to_hashable(r) for r in rows_a) == Counter(to_hashable(r) for r in rows_b)


def run_sql(db_path: Path, sql: str) -> list:
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA query_only = ON;")
        return list(con.execute(sql).fetchall())
    finally:
        con.close()


def validate(schema_ddl: str, sql: str) -> tuple[bool, str]:
    payload = json.dumps({"schema_ddl": schema_ddl, "sql": sql})
    r = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "validate_sql.py"), payload],
        capture_output=True, text=True,
    )
    import re
    m = re.search(r'\{.*\}', r.stdout, re.DOTALL)
    if m:
        obj = json.loads(m.group(0))
        return obj.get("ok", False), obj.get("error", "")
    return False, "validate_sql.py produced no output"


def test_task(task: dict, sql_override: str | None = None) -> dict:
    task_id = task["task_id"]
    db_path = REPO_ROOT / task["db_path"]
    schema  = task["db_schema"]
    gold    = task["gold_sql"]
    sql     = sql_override or gold   # 沒有 LLM 就直接用 gold 驗 harness

    result = {"task_id": task_id, "sql": sql}

    # 1. validate_sql.py
    ok, err = validate(schema, sql)
    result["validate_ok"] = ok
    result["validate_error"] = err
    if not ok:
        result["passed"] = False
        result["reason"] = f"validate failed: {err}"
        return result

    # 2. DB 執行 + bag equality
    if not db_path.exists():
        result["passed"] = False
        result["reason"] = f"db missing: {db_path}"
        return result
    try:
        student_rows = run_sql(db_path, sql)
        gold_rows    = run_sql(db_path, gold)
    except sqlite3.Error as e:
        result["passed"] = False
        result["reason"] = f"SQL error: {e}"
        return result

    passed = bag_equal(student_rows, gold_rows)
    result["passed"] = passed
    result["student_rows"] = len(student_rows)
    result["gold_rows"]    = len(gold_rows)
    result["reason"] = "" if passed else "bag equality failed"
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", help="path to a single task JSON file")
    p.add_argument("--sql",  help="SQL to test (default: use gold_sql)")
    args = p.parse_args()

    if args.task:
        tasks = [json.loads(Path(args.task).read_text())]
    else:
        tasks = sorted(
            (REPO_ROOT / "dev_set" / "basic").glob("task_nl2sql_[0-9]*.json"),
            key=lambda f: f.name,
        )
        tasks = [json.loads(f.read_text()) for f in tasks]

    passed = 0
    for t in tasks:
        r = test_task(t, args.sql)
        mark = "OK " if r["passed"] else "ERR"
        detail = f"  rows={r.get('student_rows','?')}/{r.get('gold_rows','?')}" if r["passed"] else f"  {r['reason']}"
        print(f"[{mark}] {r['task_id']}{detail}")
        if r["passed"]:
            passed += 1

    print(f"\n{passed}/{len(tasks)} passed")
    return 0 if passed == len(tasks) else 1


if __name__ == "__main__":
    sys.exit(main())
