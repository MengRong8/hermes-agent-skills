---
name: bug-hunter-MengRong8
description: Audit a Python function for bugs against its task description; emit a structured bug report per the AIASE 2026 Pairwise Bug Hunter output contract. False positives on clean code are penalized.
version: 0.2.0
metadata:
  hermes:
    tags: [code, audit, aiase-2026]
    category: code
---

# Bug Hunter Skill (Pairwise Track)

## When to Use

Triggered when the user sends a JSON payload containing `task_id`, `task_description`, and `code`. Produce a precise bug report. **False positives on clean code directly reduce your score** (25% of grade).

Trigger example:
```
/bug-hunter-MengRong8 {"task_id":"task_pair_001","task_description":"Implement merge_intervals(intervals): given a list of [start,end] integer intervals return merged non-overlapping intervals sorted by start. Empty input returns [].","code":"def merge_intervals(intervals):\n    intervals.sort(key=lambda x: x[0])\n    result = [intervals[0]]\n    for i in intervals[1:]:\n        if i[0] <= result[-1][1]:\n            result[-1][1] = max(result[-1][1], i[1])\n        else:\n            result.append(i)\n    return result"}
```

## Scoring Rules (critical to understand)

| Source | Weight | What it tests |
|---|---|---|
| TA's buggy code | 50% | Did you find the real bugs? |
| TA's clean code | 25% | Do you avoid false positives? |
| Classmate's code | 25% | Practical accuracy |

**Verdict=buggy on clean code subtracts score.** Be conservative: only report bugs you can demonstrate.

## Procedure

> **IMPORTANT — terminal environment notes**:
> 1. Do **NOT** use `cd`, do **NOT** set `workdir`, do **NOT** run `pwd` or `ls` to verify the directory.
> 2. The terminal may show `/bin/bash: line 1: cd: <some-windows-path>: No such file or directory` with `exit_code: 126`. This means the terminal is unavailable in this environment.
> 3. **If the terminal is unavailable (exit_code 126 on any command)**: skip ALL script steps, use static analysis only (Steps 2 and 4), and output the result JSON **directly in your response** as a fenced code block. Do NOT attempt any more terminal calls. Just write the JSON:
> ```json
> {
>   "task_id": "<task_id from input>",
>   "verdict": "clean or buggy",
>   "bugs": [],
>   "confidence": 0.6
> }
> ```
> The evaluator will read this block directly. This is the correct fallback behaviour.

### Step 1 — Parse the payload

Read:
- `task_id` (required for output)
- `task_description` (the specification the code is supposed to satisfy)
- `code` (Python source string, 1-indexed lines)

Extract the entry function name from `code` using the first top-level `def` statement. This is the function under test.

### Step 2 — Static review (read the code)

Read the code line by line. Check for:

**Edge case bugs:**
- Is there an empty-input guard? (`if not x: return []` / `if not s: return ""`)
- Does the code access `x[0]` before checking `len(x) > 0`? → `IndexError` on empty input (type: `edge_case`)
- Does it dereference `.left` / `.right` / `.next` without None check? → `null_deref`

**Off-by-one bugs:**
- `range(n)` vs `range(n+1)` — test the boundary manually
- `<` vs `<=` in comparisons — especially for touching intervals/ranges (spec says "touching" → `<=`)
- `[-1]` vs `[0]` indexing — look at return value construction

**Logic errors:**
- Wrong sort key
- Appending instead of merging / updating in place vs returning new
- Missing `sorted()` call when the spec says "return sorted"
- Wrong aggregation (`min` instead of `max`, `+` instead of `-`)

**Type errors:**
- Returns `tuple` when spec says list
- Returns `str` when spec says list of strings
- Integer division when float expected

**Unhandled input:**
- `None` passed instead of `[]`
- Single-element input handled by a loop that doesn't run (ok usually, but check return)
- A required input variant is entirely absent from the code (e.g., spec says "support quoted fields containing commas" but code only splits on `,` with no quoting logic) → `unhandled_input`, point to the **specific condition** that fails to account for that variant (e.g., the `if c == ','` that ignores quote context), NOT the enclosing `for`/`while` loop line

### Step 3 — Dynamic probing with the harness

Run the analyzer:

```
python skills/bug-hunter-MengRong8/scripts/analyze.py '<probe_payload>'
```

where `probe_payload` is:
```json
{
  "code": "<code from input>",
  "entry_function": "<entry function name you extracted>",
  "edge_inputs": [
    {"input": [[]], "label": "empty list"},
    {"input": [null], "label": "None"},
    {"input": [[[1,2]]], "label": "single interval"},
    {"input": [[[1,3],[2,4]]], "label": "overlapping pair"},
    {"input": [[[1,2],[2,3]]], "label": "touching pair"},
    {"input": [[[3,4],[1,2]]], "label": "unsorted input"}
  ]
}
```

Adapt `edge_inputs` to the actual function signature. For a string function:
```json
{"input": [""], "label": "empty string"},
{"input": ["a"], "label": "single char"}
```
For an integer function:
```json
{"input": [0], "label": "zero"},
{"input": [-1], "label": "negative"}
```

The harness returns:
```json
{
  "entry_found": true,
  "ast_lines": {"entry_def": 1, "return_lines": [5,8], "loop_lines": [3,4]},
  "probes": [{"label": "empty list", "outcome": "crash", "error": "IndexError: list index out of range", "bad_line": 2}],
  "suspicious_lines": [2],
  "summary": "10 probes; 1 crash, 0 timeout, 9 ok; suspicious_lines=[2]"
}
```

### Step 4 — Synthesize evidence and decide

Use a 3-level decision process:

**Level A — Crash evidence (high confidence):**
- Any `outcome: "crash"` with `bad_line > 0` → real bug. The crash line IS the bug location.
- `IndexError` on empty list at line N → `edge_case`, severity `medium`
- `AttributeError: NoneType` at line N → `null_deref`, severity `high`
- `TypeError` on wrong arg type → `type_error`, severity `medium`

**Level B — Static analysis (medium confidence):**
- You found a `<` where spec requires `<=` (touching check) → `off_by_one`, severity `high`
- Wrong sort key (`x[1]` instead of `x[0]`) → `logic_error`, severity `high`
- Missing return value (`return None` implicitly when non-empty) → `logic_error`, severity `critical`

**Level C — Suspicion only (low confidence — do NOT report):**
- "The code looks inefficient" → only report as `inefficient` if provably O(n²) when O(n) required
- "The variable name is confusing" → not a bug
- "I would write it differently" → not a bug
- No crash and logic seems correct → `verdict: clean`

**Decision rule:**
- Level A crash on a test case → `verdict: buggy`
- Level B with clear spec violation → `verdict: buggy`
- Level C only, or no evidence → `verdict: clean`

### Step 5 — Build the bug list

For each confirmed bug:

```
line_start: first line of the buggy code (1-indexed, includes blank/comment lines)
line_end:   last line of the buggy span (usually = line_start for single-line bugs)
type:       one of: off_by_one | null_deref | type_error | logic_error | edge_case | api_misuse | inefficient | unhandled_input
severity:   critical | high | medium | low
description: what exactly is wrong, what input triggers it
suggested_fix: one specific actionable fix (e.g., "add `if not intervals: return []` before line 2")
```

**Worked example of correct `line_start` counting (this is the #1 source of lost points — read carefully):**

```
1: def f(items):
2:     out = []
3:     for x in items:
4:         if x == 0:
5:             out.append(-1)
6:         else:
7:             out.append(x)
8:     return out
```

If the spec requires special handling for negative `x` and the code has none, the missing
case lives in the **condition that should have branched on it** — `line_start = 4` (the
`if x == 0:` line), **not** `line_start = 3` (the `for x in items:` line that merely iterates).
The grader does an **exact-line match**, so being one line off (pointing at the loop header,
or at the `else:` line, or at the line *after* the relevant condition) scores as a complete
miss even when your description and `type` are both correct. Before writing `line_start`,
count the lines of the `code` string yourself starting at `1` for the `def` line, find the
single line whose condition/check is the one that's missing or wrong, and use exactly that
line number — never the loop/function line that merely contains it.

**Severity calibration:**
| Trigger | Severity |
|---|---|
| Crashes on any non-empty valid input | `critical` |
| Wrong answer on common non-edge input | `high` |
| Crashes only on empty/None input | `medium` |
| Wrong answer only on rare edge case | `medium` |
| Performance issue (wrong complexity) | `low` |
| Minor style issue | not a bug |

**If `verdict: clean`**: `bugs` MUST be `[]`.

### Step 6 — Emit the output contract

Run:
```
python skills/bug-hunter-MengRong8/scripts/run.py '<json_payload>'
```

where `json_payload` is:
```json
{
  "task_id": "<task_id from input>",
  "verdict": "buggy" or "clean",
  "bugs": [
    {
      "line_start": <int>,
      "line_end": <int>,
      "severity": "critical|high|medium|low",
      "type": "off_by_one|null_deref|type_error|logic_error|edge_case|api_misuse|inefficient|unhandled_input",
      "description": "<what is wrong and what triggers it>",
      "suggested_fix": "<specific actionable fix>"
    }
  ],
  "confidence": <0.8-0.95 if crash evidence; 0.6-0.8 if static only; 0.4-0.5 if uncertain>
}
```

Output the fenced ```json``` block **exactly as printed** — do not modify it.

## Pitfalls

| Pitfall | How to avoid |
|---|---|
| Reporting "inefficient" without proof | Only report if provably wrong Big-O, e.g. O(n²) sort in a loop |
| Wrong line numbers (0-indexed) | Lines are 1-indexed; count from top of the `code` string |
| Reporting style issues | "This could be written cleaner" is not a bug |
| `verdict=clean` with non-empty bugs | The harness enforces this; run.py will clear bugs if verdict=clean |
| Over-reporting (5+ bugs) | Real code rarely has more than 1-2 bugs; pick the most certain ones |
| Under-reporting (always clean) | You WILL see crashes in probes for buggy code; trust them |
| Pointing at function def line | Bug line is where the wrong logic IS, not the function header |
| Pointing at loop header instead of condition | If the bug is inside a loop, `line_start` should be the specific `if`/comparison that is wrong, not the `for`/`while` line that wraps it |
| `logic_error` vs `unhandled_input` | If the spec requires handling a class of input (e.g. quoted fields, unicode, negatives) and the code has **zero handling** for it, use `unhandled_input`; use `logic_error` only when the code attempts handling but does it incorrectly |

## Verification

The final output of `scripts/run.py` is a single fenced `json` block containing:
- `task_id` (string, matches input)
- `verdict` (`"buggy"` or `"clean"`)
- `bugs` (array; `[]` when `verdict=clean`)
- `confidence` (float in `[0.0, 1.0]`)
