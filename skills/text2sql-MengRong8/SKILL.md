---
name: text2sql-MengRong8
description: Convert a natural-language question + SQLite schema into a verified read-only SQL query. AIASE 2026 Basic Track.
version: 0.1.0
metadata:
  hermes:
    tags: [sql, text2sql, data, aiase-2026]
    category: data
---

# Text2SQL Skill (Basic Track)

## When to Use

When the user sends a JSON payload with `question`, `db_schema` (SQLite DDL), and optional `task_id` + `dialect`. The skill must produce a single read-only SQLite query whose result on the hidden DB matches the gold answer under **bag equality** (order-insensitive multiset comparison).

Trigger example:

```
/text2sql-MengRong8 {"task_id":"task_nl2sql_017",
  "question":"For each department, return its name and the total number of appointments ...",
  "db_schema":"CREATE TABLE Departments(...); ...", "dialect":"sqlite"}
```

## Procedure

> **IMPORTANT — terminal environment notes**:
> 1. Do **NOT** use `cd`, do **NOT** set `workdir`, do **NOT** run `pwd` or `ls` to verify the directory.
> 2. The terminal may show `/bin/bash: line 1: cd: <some-windows-path>: No such file or directory` with `exit_code: 126`. This means the terminal is unavailable in this environment.
> 3. **If the terminal is unavailable (exit_code 126 on any command)**: skip ALL script steps and output the result JSON **directly in your response** as a fenced code block. Do NOT attempt any more terminal calls. Just write the JSON:
> ```json
> {
>   "task_id": "<task_id from input>",
>   "sql": "<your SQL query>",
>   "rationale": "<one sentence>",
>   "confidence": 0.7
> }
> ```
> The evaluator will read this block directly. This is the correct fallback behaviour.

### Step 1 — Parse Input

Extract and note:
- `task_id` (copy verbatim to output — grader rejects mismatches)
- `question` (the natural-language question)
- `db_schema` (SQLite DDL — the only source of truth for table/column names)
- `dialect` (always "sqlite")

### Step 2 — Analyze Schema

Before writing SQL, map out the schema mentally:
1. List every table and its columns (with types) from the DDL.
2. Identify foreign-key relationships (look for columns like `_id` suffixes or explicit REFERENCES).
3. Note which tables are bridge/junction tables (two FK columns, no other payload).

### Step 3 — Plan the SQL Using the Decision Guide Below

Read the question carefully. Apply the pattern rules in **SQL Pattern Cheatsheet** to decide:
- Which tables to join and what JOIN type (INNER vs LEFT)
- Whether DISTINCT is needed
- Whether aggregation / HAVING / ORDER BY / LIMIT are needed
- Whether subqueries or UNION are required

### Step 4 — Draft SQL

Write a single SQLite SELECT statement. Rules:
- **No** `WITH` / CTE, no window functions, no recursive queries
- **No** `INSERT` / `UPDATE` / `DELETE` / DDL
- **No** multiple statements (no second semicolon)
- Table/column names must exactly match the DDL (case-insensitive in SQLite, but use the exact case from DDL to be safe)
- When in doubt, prefer alias every table: `FROM Students s JOIN Enrollments e ON s.sid = e.sid`

### Step 5 — Validate

Run the validator:

```
python skills/text2sql-MengRong8/scripts/validate_sql.py '{"schema_ddl": "<db_schema>", "sql": "<your draft sql>"}'
```

The script prints `{"ok": true, "error": ""}` on success, or `{"ok": false, "error": "<message>"}` on failure.

**If `ok=false`**: read the error message carefully and fix the specific issue:
- `"no such column"` → check the exact column name in the DDL; use the correct table alias
- `"no such table"` → check the table name spelling
- `"SQL did not compile"` → check syntax (missing ON clause, mismatched parentheses, etc.)
- `"multiple SQL statements"` → remove the trailing semicolon or merge statements
- `"DDL/DML/PRAGMA not allowed"` → you used a forbidden keyword; rewrite as SELECT only

Retry up to **3 times**, fixing the error each time. After 3 failures, use the best draft and set `confidence` to 0.3.

### Step 6 — Emit Output Contract

Once the SQL passes validation (or after exhausting retries), run:

```
python skills/text2sql-MengRong8/scripts/run.py '{"task_id":"<task_id>","sql":"<sql>","rationale":"<one-sentence explanation>","confidence":<0.0-1.0>}'
```

The script prints a single fenced `json` block — return that block **unchanged** as your final response. Do NOT add any text after it.

---

## SQL Pattern Cheatsheet

Use this section to decide which SQL construct to use.

### DISTINCT vs no DISTINCT

| Situation | Action |
|---|---|
| Question says "distinct", "unique", "different" | Add `SELECT DISTINCT` |
| Joining through a bridge/junction table and asking for parent-entity names | Add `SELECT DISTINCT` (each parent can have multiple bridge rows) |
| Simple join where PK guarantees one row per entity | No DISTINCT needed |
| `UNION` (not `UNION ALL`) | No extra DISTINCT needed; UNION deduplicates automatically |

**Rule of thumb**: If you JOIN through a table that can produce multiple rows per entity (OrderItems, BookAuthors, Enrollments, Goals), and the question asks for entity names (not counts), use DISTINCT.

### INNER JOIN vs LEFT JOIN

| Situation | Action |
|---|---|
| "Return X who have at least one Y" | `INNER JOIN` |
| "Return all X (including those with no Y)" | `LEFT JOIN` |
| "Include X with zero Y" / "Include X with count of 0" | `LEFT JOIN` |
| "Return X who have never Y" / "Return X with no Y" | `LEFT JOIN ... WHERE Y.key IS NULL` **or** `WHERE X.id NOT IN (SELECT ...)` |

**Example — zero-count**: "For each department, return its name and the total number of appointments (include departments with zero)":
```sql
SELECT d.name, COUNT(a.aid)
FROM Departments d
LEFT JOIN Doctors doc ON d.did = doc.did
LEFT JOIN Appointments a ON doc.doc_id = a.doc_id
GROUP BY d.did, d.name
```

**Example — anti-join (who have never)**: "Return customers who have not placed any orders":
```sql
SELECT c.name FROM Customers c
LEFT JOIN Orders o ON c.cid = o.cid
WHERE o.oid IS NULL
```

### Aggregation and HAVING

| Situation | Action |
|---|---|
| "How many", "total", "average", "sum", "max/min" | Use `COUNT`, `SUM`, `AVG`, `MAX`, `MIN` |
| "For each X" + aggregate | `GROUP BY X.pk, X.name` (always include PK in GROUP BY) |
| "Return X where aggregate > N" | Add `HAVING COUNT(...) > N` (not WHERE) |
| Comparing one aggregate to another aggregate | Use a subquery in HAVING or WHERE |

**Example — HAVING with subquery**: "students whose highest score exceeds the average of course X":
```sql
SELECT s.name FROM Students s
JOIN Enrollments e ON s.sid = e.sid
GROUP BY s.sid, s.name
HAVING MAX(e.score) > (
  SELECT AVG(score) FROM Enrollments
  WHERE cid = (SELECT cid FROM Courses WHERE title = 'X')
)
```

### TOP-N / ORDER BY / LIMIT

| Situation | Action |
|---|---|
| "Top N by X" / "N highest/lowest" | `ORDER BY X DESC/ASC LIMIT N` |
| "Sort by X ascending/descending" | `ORDER BY X ASC/DESC` |
| "Return all tied" for a max/min | Use subquery: `WHERE val = (SELECT MAX(val) FROM ...)` |

**Example — return all tied winners**:
```sql
SELECT t.name FROM Teams t
WHERE t.tid IN (
  SELECT home_tid FROM Games
  GROUP BY home_tid
  HAVING COUNT(*) = (
    SELECT MAX(c) FROM (
      SELECT COUNT(*) AS c FROM Games GROUP BY home_tid
    )
  )
)
```

### NOT IN / NOT EXISTS

| Situation | Action |
|---|---|
| "Return X not in set Y" | `WHERE X.id NOT IN (SELECT id FROM Y WHERE ...)` |
| "Return X who have none of Y" | `NOT IN` subquery or `LEFT JOIN ... WHERE IS NULL` |
| Universal: "Return X where **every** related Y satisfies condition" | Double-negative `NOT EXISTS ... NOT EXISTS` |

**Example — universal quantifier** ("players who scored in every home game of their team"):
```sql
SELECT p.name FROM Players p
WHERE NOT EXISTS (
  SELECT 1 FROM Games g
  WHERE g.home_tid = p.tid
  AND NOT EXISTS (
    SELECT 1 FROM Goals go
    WHERE go.gid = g.gid AND go.pid = p.pid
  )
)
```

This pattern: "X such that there is NO game g where X did NOT score in g" = "X scored in every game".

### UNION

| Situation | Action |
|---|---|
| "Return X OR Y" where X and Y come from different join paths | `SELECT ... UNION SELECT ...` |
| "Return set A plus set B" (both sets have same column structure) | `SELECT ... UNION SELECT ...` |
| Want to keep duplicates between the two sets | `UNION ALL` |

**Note**: UNION (without ALL) automatically removes duplicates across the two result sets.

---

## Pitfalls

- **Missing DISTINCT on bridge-table JOINs**: If you JOIN through BookAuthors or OrderItems and ask for author/product names, you'll get duplicates. Bag equality counts duplicates — extra rows = wrong answer.
- **INNER JOIN when question needs zero-count rows**: "Include departments with zero appointments" requires LEFT JOIN chain. INNER JOIN silently drops those rows.
- **Wrong GROUP BY**: Always include the primary key in GROUP BY alongside the display column (e.g., `GROUP BY s.sid, s.name` not just `GROUP BY s.name` — two different students can share a name).
- **CTE / WITH**: Forbidden. Rewrite as a subquery.
- **Window functions**: Forbidden. Use subqueries instead.
- **task_id mismatch**: Copy the `task_id` from input verbatim — any change causes grader rejection.
- **Trailing semicolon in multi-statement check**: `validate_sql.py` rejects `";"` inside the SQL body. Strip the trailing semicolon before passing.
- **Subquery column name collision**: Give unique aliases to subquery tables; SQLite can be confused by unaliased inner tables sharing names with outer tables.
- **`OR` condition needing UNION**: If the question says "OR" between two independent set conditions (each requiring different join paths), `WHERE p.category = 'A' OR p.category = 'B'` works, but "customers who bought from Electronics OR customers who bought from Books" may need UNION if the path is different. When in doubt, use a single `WHERE ... IN ('A','B')` or `UNION`.

## Verification

The output of `scripts/run.py` is a single fenced `json` block with:

- `task_id` (must equal input)
- `sql` (single read-only SQLite SELECT query)
- `rationale` (one sentence explaining the approach)
- `confidence` (number in `[0.0, 1.0]` — lower if validation failed or logic is uncertain)

This block must be the **last** fenced JSON in your stdout. Return it unchanged. Do not add any reasoning, prose, or additional fenced blocks after it.
