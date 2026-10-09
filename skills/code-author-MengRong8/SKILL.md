---
name: code-author-MengRong8
description: Implement a Python function from a natural-language task description, self-test against sample inputs, and emit the AIASE 2026 Pairwise Code Author output contract.
version: 0.2.0
metadata:
  hermes:
    tags: [code, python, aiase-2026]
    category: code
---

# Code Author Skill (Pairwise Track)

## When to Use

Triggered when the user sends a JSON payload containing `task_id`, `task_description`, and `constraints`. Produce a Python implementation that passes all hidden test cases.

Trigger example:
```
/code-author-MengRong8 {"task_id":"task_pair_001","task_description":"Implement merge_intervals(intervals): given a list of [start,end] integer intervals return merged non-overlapping intervals sorted by start. Empty input returns [].","constraints":{"entry_function":"merge_intervals","max_loc":500,"imports_forbidden":["os","sys","subprocess"]},"sample_tests":[{"input":[[]],"expected":[]},{"input":[[[1,3],[2,4]]],"expected":[[1,4]]}]}
```

## Procedure

> **IMPORTANT — terminal environment notes**:
> 1. Do **NOT** use `cd`, do **NOT** set `workdir`, do **NOT** run `pwd` or `ls` to verify the directory.
> 2. The terminal may show `/bin/bash: line 1: cd: <some-windows-path>: No such file or directory` with `exit_code: 126`. This means the terminal is unavailable in this environment.
> 3. **If the terminal is unavailable (exit_code 126 on any command)**: skip ALL script steps and output the result JSON **directly in your response** as a fenced code block. Do NOT attempt any more terminal calls. Just write the JSON:
> ```json
> {
>   "task_id": "<task_id from input>",
>   "code": "<your implementation as a Python string>",
>   "loc": 10,
>   "self_test_results": {"passed": 0, "failed": 0},
>   "rationale": "<one sentence>",
>   "confidence": 0.6
> }
> ```
> The evaluator will read this block directly. This is the correct fallback behaviour.

### Step 1 — Parse the payload

Read and record from the JSON input:
- `task_id` (string, required for output)
- `task_description` (full natural-language spec)
- `constraints.entry_function` (the exact function name to define)
- `constraints.max_loc` (default 500 if absent)
- `constraints.imports_forbidden` (list of modules you must NOT import)
- `sample_tests` (list of `{input, expected}` — use as self-test cases)

### Step 2 — Understand the spec

Before writing code, answer these questions:
1. **Input type**: single argument or multiple? list, string, int, dict?
2. **Output type**: list, string, int, bool?
3. **Edge cases defined by spec**: empty input, None, single element, duplicates, already-sorted, all-same?
4. **Touching vs overlapping**: for interval/range tasks, re-read the spec sentence about equality (e.g. `<=` vs `<`).
5. **Return type**: mutable list vs tuple? nested or flat?
6. **Expected input size / complexity budget**: the grader runs each hidden test with a **5-second timeout and 512 MB memory limit** (spec §2.3) — a correct-but-too-slow answer scores **0 on that test**, same as a wrong answer. If the spec implies non-trivial N (counts, "large", "all pairs", repeated lookups), default to `O(n log n)` or `O(n)`; use `set`/`dict` for membership/lookup instead of scanning a `list` inside a loop (the most common accidental `O(n^2)`). Only accept `O(n^2)` or worse if the task is inherently quadratic (e.g. literally comparing all pairs) AND N is implied to be small.

### Step 3 — Write the implementation

Rules:
- Define exactly `constraints.entry_function` as the top-level function name. Do **not** rename it.
- Use only stdlib modules that are NOT in `imports_forbidden`. If no imports needed, use none.
- Do NOT use: `os`, `sys`, `subprocess`, nor any dynamic `__import__`. Check `imports_forbidden`.
- Handle **all edge cases**: empty input (`[]`/`""`/`0`/`None`), single element, duplicates.
- Keep code concise. The SLOC limit is `max_loc` (default 500). Use `radon raw` measurement.
- No network, no filesystem reads outside cwd, no dynamic import.
- Avoid unnecessary nested loops / repeated linear scans (see Step 2 Q6) — a 5s/test timeout means a too-slow-but-correct algorithm gets 0 credit on that test.

Common safe imports: `collections`, `heapq`, `itertools`, `functools`, `math`, `re`, `copy`, `typing`

### Step 4 — Self-test with the harness

Build a `selftest_payload` JSON and run the harness:

```
python skills/code-author-MengRong8/scripts/selftest.py '<selftest_payload>'
```

where `selftest_payload` is:
```json
{
  "code": "<your implementation as a string>",
  "constraints": {
    "entry_function": "<constraints.entry_function>",
    "max_loc": <constraints.max_loc or 500>,
    "imports_forbidden": <constraints.imports_forbidden or []>
  },
  "sample_inputs": <sample_tests from payload, or [] if absent>
}
```

The harness returns a fenced JSON block:
```json
{
  "passed": <int>,
  "failed": <int>,
  "errors": ["<error messages>"],
  "sloc": <int>,
  "loc_violation": <bool>,
  "import_violations": ["<module names>"],
  "max_elapsed_sec": <float>,
  "slow_warning": <bool>
}
```

`max_elapsed_sec` is the slowest sample's wall-clock time; the harness fails any sample
that takes longer than its own 2s self-test budget (a `timeout:` entry in `errors`) — this
is deliberately tighter than the grader's 5s/test so a complexity problem is caught locally
on small sample inputs before it would fail on larger hidden-test inputs.
`slow_warning: true` means a sample passed but took 0.5–2s on what is likely a tiny input —
treat this the same as a real failure and rewrite with a better algorithm, not a fail to ignore.

### Step 5 — Fix and retry (up to 3 rounds)

If `failed > 0` OR `loc_violation == true` OR `import_violations` is non-empty OR `slow_warning == true`:

1. Read each `errors[i]` message carefully.
2. Identify the bug: off-by-one, missing edge case, wrong return type, forbidden import, algorithmic complexity, etc.
3. Fix the code and re-run selftest.
4. Repeat up to **3 rounds** total. After 3 failed rounds, keep the best attempt.

Common fix patterns:
- `entry function 'X' not defined` → function name typo; rename to match `entry_function` exactly.
- `mismatch on [[]]: got None, expected []` → missing `if not x: return []` guard.
- `mismatch on [[1,2]]: got [[1,2]], expected [[1,2]]` → check list vs tuple, int vs float.
- `loc_violation: true` → remove docstrings, inline helper lambdas, simplify control flow.
- `import_violations: ["os"]` → remove that import entirely.
- `timeout:` error or `slow_warning: true` → re-derive the algorithm's Big-O; replace nested loops / repeated `in` checks on a `list` with a single pass using `set`/`dict`, or use `sorted()` + two-pointer instead of comparing all pairs.

### Step 6 — Emit the output contract

Run:
```
python skills/code-author-MengRong8/scripts/run.py '<json_payload>'
```

where `json_payload` is:
```json
{
  "task_id": "<task_id from input>",
  "code": "<final implementation string>",
  "loc": <sloc from last selftest>,
  "self_test_results": {
    "passed": <passed>,
    "failed": <failed>
  },
  "rationale": "<1-2 sentence: what algorithm, what edge cases handled>",
  "confidence": <0.7-0.95 if all tests pass; 0.4-0.6 if some failed>
}
```

Output the fenced ```json``` block **exactly as printed** — do not modify it.

## Pitfalls

| Pitfall | How to avoid |
|---|---|
| Wrong function name | Copy `constraints.entry_function` literally; do not alias |
| Missing empty-input guard | Always test `[]`, `""`, `0`, `None` before loop/index |
| Off-by-one in range/slice | Test endpoint `[n-1]`, `[0]`, inclusive vs exclusive boundary |
| Touching intervals (<=) vs overlapping (<) | Re-read spec; test `[1,2],[2,3]` |
| `loc_violation` due to docstring | Remove triple-quoted docstrings; use no-comment approach |
| Forbidden import silently used | `selftest.py` catches it via AST; trust the harness |
| `got [[1,4]], expected [[1, 4]]` | List equality is deep; integer vs float mismatch also fails |
| Dynamic import (`__import__`, `importlib`) | Forbidden; avoid entirely |
| Nested loop / repeated linear scan over the same data | Grader gives 0 credit on a timed-out test even if logic is correct; use `set`/`dict` lookups or sort + single pass instead of `O(n^2)`/`O(n^3)` |

## Verification

The final output of `scripts/run.py` is a single fenced `json` block containing:
- `task_id` (string, matches input)
- `code` (string, valid Python defining `entry_function`)
- `loc` (integer, SLOC as measured by harness)
- `self_test_results` (object with `passed` and `failed`)
- `rationale` (string)
- `confidence` (float in `[0.0, 1.0]`)
