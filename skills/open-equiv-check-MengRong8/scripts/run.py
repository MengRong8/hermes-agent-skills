#!/usr/bin/env python3
"""
run.py — Emit the final equivalence-checking result per AIASE output contract.

Usage:
    python skills/open-equiv-check-MengRong8/scripts/run.py '<json_payload>'

Required fields: task_id, equivalent, confidence
Optional field:  counterexample (required when equivalent=false)
"""
import json
import os
import sys
from pathlib import Path


def emit_contract(result: dict) -> None:
    result_str = json.dumps(result, ensure_ascii=False, indent=2)

    rp   = os.environ.get("AIASE_RESULT_PATH")
    dest = Path(rp) if rp else Path("./aiase_result.json")
    try:
        dest.write_text(result_str, encoding="utf-8")
    except OSError:
        pass

    print("```json")
    print(result_str)
    print("```")

def _fallback(task_id: str = "") -> None:
    # Output contract requires a fenced json block on every path, even on
    # malformed input — an unfenced error object would give the grader's
    # last-fenced-block extractor nothing to find.
    emit_contract({
        "task_id": task_id,
        "equivalent": False,
        "counterexample": None,
        "confidence": 0.0,
    })


def main() -> None:
    if len(sys.argv) < 2:
        _fallback()
        return

    try:
        payload = json.loads(sys.argv[1])
        if not isinstance(payload, dict):
            raise ValueError("payload not an object")
    except (json.JSONDecodeError, ValueError):
        _fallback()
        return

    task_id = str(payload.get("task_id", ""))

    required = ["equivalent", "confidence"]
    missing  = [f for f in required if f not in payload]
    if missing:
        _fallback(task_id)
        return

    equivalent = bool(payload["equivalent"])
    if not equivalent and "counterexample" not in payload:
        _fallback(task_id)
        return

    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    emit_contract({
        "task_id":        task_id,
        "equivalent":     equivalent,
        "counterexample": payload.get("counterexample"),  # null when equivalent=true
        "confidence":     confidence,
    })


if __name__ == "__main__":
    main()
