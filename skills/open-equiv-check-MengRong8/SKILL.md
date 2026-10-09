---
name: open-equiv-check-MengRong8
description: "Given two Python functions that claim to implement the same specification, determine whether they are semantically equivalent. If not equivalent, provide a concrete counterexample (input + both outputs) and verify it via equiv_checker.py."
version: 1.0.0
metadata:
  hermes:
    tags: [equivalence, testing, code-analysis, aiase-2026]
    category: code
---

# Function Equivalence Checker (Open Track)

## When to Use

Triggered when the user sends a JSON payload with `task_id`, `description` (the spec both functions must satisfy), `func_a` (Python source string), and `func_b` (Python source string).

Trigger example:
```
/open-equiv-check-MengRong8 {"task_id":"open_equiv_001","description":"count_down(n) returns a list [n, n-1, ..., 1]","func_a":"def count_down(n):\n    return list(range(n, 0, -1))","func_b":"def count_down(n):\n    return list(range(n-1, 0, -1))","entry":"count_down"}
```

## Output Contract

The final output MUST be a single fenced ` ```json ` block containing:
```json
{
  "task_id": "<same as input>",
  "equivalent": true,
  "counterexample": null,
  "confidence": 0.85
}
```
or, when not equivalent:
```json
{
  "task_id": "<same as input>",
  "equivalent": false,
  "counterexample": {
    "input": [3],
    "output_a": [3, 2, 1],
    "output_b": [2, 1]
  },
  "confidence": 0.95
}
```

---

## Procedure

> **IMPORTANT — terminal environment notes**:
> 1. Do **NOT** use `cd`, do **NOT** set `workdir`.
> 2. If terminal shows `/bin/bash: line 1: cd: <path>: No such file or directory` with `exit_code: 126`, the terminal is **unavailable**.
> 3. **If terminal unavailable**: skip Steps 3–4. Use only static analysis (Step 2). Output result JSON directly in your response with `confidence: 0.6`. Do NOT attempt further terminal calls.

### Step 1 — Parse the input

Read from the JSON payload:
- `task_id` — copy verbatim to output
- `description` — the shared specification both functions must satisfy
- `func_a` — Python source of the first function
- `func_b` — Python source of the second function
- `entry` — the entry function name (same for both)

### Step 2 — Static analysis: find candidate differences

Read both functions line by line. Look for divergence in:

| Category | What to look for |
|---|---|
| **Off-by-one** | `range(n)` vs `range(n+1)`, `<` vs `<=`, `[k]` vs `[k-1]` |
| **Logic operator** | `and` vs `or`, `==` vs `!=`, `+` vs `-` |
| **Missing guard** | One handles empty input, the other doesn't |
| **Different algorithm** | Same result but different method → likely equivalent |
| **Return type** | One returns list, other returns generator / tuple |

If you spot a structural difference, immediately form a hypothesis:
> "The functions differ when input = X, because func_a does Y but func_b does Z."

### Step 3 — Probe with equiv_checker.py

Build a test suite focused on your hypotheses plus standard edge cases:

```
python skills/open-equiv-check-MengRong8/scripts/equiv_checker.py '<probe_payload>'
```

where `<probe_payload>` is:
```json
{
  "func_a_code": "<func_a from input>",
  "func_b_code": "<func_b from input>",
  "entry_a": "<entry>",
  "entry_b": "<entry>",
  "test_cases": [
    {"input": [<hypothesis input>], "label": "hypothesis case"},
    {"input": [0],  "label": "zero"},
    {"input": [1],  "label": "single element"},
    {"input": [-1], "label": "negative"},
    {"input": [],   "label": "empty"},
    {"input": [10], "label": "medium"}
  ]
}
```

Adapt `test_cases` to the actual function signature (e.g., for string input: `{"input": [""], "label": "empty string"}`).

**Interpret results:**
- `all_equal: false` → `first_difference` is your confirmed counterexample. Proceed to Step 5.
- `all_equal: true` → functions agree on all probes. Try Step 4.

### Step 4 — Extended probing (if Step 3 found no difference)

Run a second round with more diverse inputs (larger values, boundary extremes, corner cases). If still `all_equal: true` across ≥ 8 distinct inputs → declare equivalent with `confidence: 0.8`.

### Step 5 — Build the output

**If not equivalent** (found `first_difference` from equiv_checker):
```json
{
  "task_id": "<task_id>",
  "equivalent": false,
  "counterexample": {
    "input":    <first_difference.input>,
    "output_a": <first_difference.output_a>,
    "output_b": <first_difference.output_b>
  },
  "confidence": 0.95
}
```

**If equivalent** (no difference found after ≥ 8 probes):
```json
{
  "task_id": "<task_id>",
  "equivalent": true,
  "counterexample": null,
  "confidence": 0.8
}
```

### Step 6 — Emit via run.py

```
python skills/open-equiv-check-MengRong8/scripts/run.py '<result_payload>'
```

Output the fenced ` ```json ` block **exactly as printed by run.py**.

---

## Verification

The evaluator verifies the output as follows:

- **If `equivalent: false`**: Takes `counterexample.input` from your output and runs `equiv_checker.py` with just that one test case. If `all_equal: false` → PASS. If `all_equal: true` → FAIL (false counterexample).
- **If `equivalent: true`**: Runs `equiv_checker.py` with 20 diverse test cases. If `all_equal: true` → PASS. If any differ → FAIL (missed a difference).

## Pitfalls

| Pitfall | How to avoid |
|---|---|
| Shallow probe (only 1–2 cases) | Always include edge cases: 0, 1, empty, negative, large value |
| Guessing counterexample without verifying | Always run equiv_checker.py first; never fabricate output_a/output_b |
| `equivalent: false` with `counterexample: null` | run.py enforces this; will error if counterexample missing |
| Reporting semantics as equivalent when one crashes | equiv_checker detects crash-vs-return as a difference |
