<!--
   Open Track 宣告 — 七個 heading 請照抄,順序也別動。
   合規判定會自動解析這七節;少一節就 fail gate。
   詳細要求見規格書 §2.4 與 §4.3。
-->

## 1. Skill 簡介

給定兩個聲稱實作同一規格的 Python 函數 `func_a` 與 `func_b`，Agent 判斷它們是否語意等價。若不等價，必須提供可執行的反例 `{input, output_a, output_b}`，並由 `scripts/equiv_checker.py` 實際執行兩函數後驗證反例的正確性。

## 2. Skill 名稱與目錄

- Skill 名稱：`open-equiv-check-MengRong8`
- 路徑：`skills/open-equiv-check-MengRong8/`
- Harness 腳本：`skills/open-equiv-check-MengRong8/scripts/equiv_checker.py`（執行驗證）、`scripts/run.py`（輸出）

## 3. 呼叫方式

**Slash command:**
```
/open-equiv-check-MengRong8
```

**完整 hermes chat 指令（評分器可直接複製）：**
```bash
hermes chat --provider aiase --toolsets skills,terminal --yolo -Q \
  -q '/open-equiv-check-MengRong8 {"task_id":"open_equiv_001","description":"count_down(n) returns a list counting from n down to 1 inclusive. count_down(3) == [3,2,1]. count_down(0) == [].","func_a":"def count_down(n):\n    return list(range(n, 0, -1))","func_b":"def count_down(n):\n    return list(range(n-1, 0, -1))","entry":"count_down"}'
```

**輸入 JSON 範例：**
```json
{
  "task_id": "open_equiv_001",
  "description": "count_down(n) returns [n, n-1, ..., 1]. count_down(0) == [].",
  "func_a": "def count_down(n):\n    return list(range(n, 0, -1))",
  "func_b": "def count_down(n):\n    return list(range(n-1, 0, -1))",
  "entry": "count_down"
}
```

**輸出 JSON Schema（不等價時）：**
```json
{
  "task_id": "open_equiv_001",
  "equivalent": false,
  "counterexample": {
    "input": [3],
    "output_a": [3, 2, 1],
    "output_b": [2, 1]
  },
  "confidence": 0.95
}
```

**輸出 JSON Schema（等價時）：**
```json
{
  "task_id": "open_equiv_002",
  "equivalent": true,
  "counterexample": null,
  "confidence": 0.85
}
```

## 4. 自定 Verifiable Scenario

**評分標準：**

- **`equivalent: false` 時**：評分器取 `counterexample.input`，執行 `equiv_checker.py` 以該 input 跑兩函數，若 `all_equal: false` → PASS；若 `all_equal: true` → FAIL（反例造假）。
- **`equivalent: true` 時**：評分器以 20 組多樣 inputs 跑 `equiv_checker.py`，若 `all_equal: true` → PASS；若有任何差異 → FAIL（漏掉 bug）。

---

### Scenario 1 — **不等價**：count_down off-by-one

**task_id:** `open_equiv_001`

**description:** `count_down(n)` returns a list counting from `n` down to `1` inclusive. `count_down(3)` must return `[3, 2, 1]`. `count_down(0)` must return `[]`.

**func_a（正確）：**
```python
def count_down(n):
    return list(range(n, 0, -1))
```

**func_b（有 bug）：**
```python
def count_down(n):
    return list(range(n - 1, 0, -1))
```

**預期輸出：** `equivalent: false`

**最小反例：** `input=[3]` → `output_a=[3,2,1]`，`output_b=[2,1]`

**驗證指令：**
```bash
python skills/open-equiv-check-MengRong8/scripts/equiv_checker.py \
  '{"func_a_code":"def count_down(n):\n    return list(range(n, 0, -1))","func_b_code":"def count_down(n):\n    return list(range(n - 1, 0, -1))","entry_a":"count_down","entry_b":"count_down","test_cases":[{"input":[3],"label":"basic"}]}'
```
期望：`all_equal: false`

---

### Scenario 2 — **等價**：digit_sum 遞迴 vs 迭代

**task_id:** `open_equiv_002`

**description:** `digit_sum(n)` returns the sum of decimal digits of non-negative integer `n`. `digit_sum(123)` == `6`. `digit_sum(0)` == `0`.

**func_a（遞迴）：**
```python
def digit_sum(n):
    if n < 10:
        return n
    return n % 10 + digit_sum(n // 10)
```

**func_b（迭代）：**
```python
def digit_sum(n):
    total = 0
    while n > 0:
        total += n % 10
        n //= 10
    return total
```

**預期輸出：** `equivalent: true`

**驗證指令：**
```bash
python skills/open-equiv-check-MengRong8/scripts/equiv_checker.py \
  '{"func_a_code":"def digit_sum(n):\n    if n < 10:\n        return n\n    return n % 10 + digit_sum(n // 10)","func_b_code":"def digit_sum(n):\n    total = 0\n    while n > 0:\n        total += n % 10\n        n //= 10\n    return total","entry_a":"digit_sum","entry_b":"digit_sum","test_cases":[{"input":[0],"label":"zero"},{"input":[9],"label":"single digit"},{"input":[123],"label":"three digits"},{"input":[999],"label":"all nines"},{"input":[1000],"label":"trailing zeros"}]}'
```
期望：`all_equal: true`

---

### Scenario 3 — **不等價**：count_fizzbuzz `and` vs `or`

**task_id:** `open_equiv_003`

**description:** `count_fizzbuzz(n)` returns how many integers from 1 to n (inclusive) are divisible by **both** 3 and 5. `count_fizzbuzz(15)` == `1` (only 15). `count_fizzbuzz(14)` == `0`.

**func_a（正確）：**
```python
def count_fizzbuzz(n):
    return sum(1 for i in range(1, n + 1) if i % 3 == 0 and i % 5 == 0)
```

**func_b（有 bug，用 or 取代 and）：**
```python
def count_fizzbuzz(n):
    return sum(1 for i in range(1, n + 1) if i % 3 == 0 or i % 5 == 0)
```

**預期輸出：** `equivalent: false`

**最小反例：** `input=[15]` → `output_a=1`，`output_b=8`

**驗證指令：**
```bash
python skills/open-equiv-check-MengRong8/scripts/equiv_checker.py \
  '{"func_a_code":"def count_fizzbuzz(n):\n    return sum(1 for i in range(1, n + 1) if i % 3 == 0 and i % 5 == 0)","func_b_code":"def count_fizzbuzz(n):\n    return sum(1 for i in range(1, n + 1) if i % 3 == 0 or i % 5 == 0)","entry_a":"count_fizzbuzz","entry_b":"count_fizzbuzz","test_cases":[{"input":[15],"label":"includes 15"}]}'
```
期望：`all_equal: false`

---

**為何不可 gameable：**

1. **counterexample 必須能執行**：`equiv_checker.py` 實際執行兩函數，模型無法「捏造」 `output_a`/`output_b`——只要輸入跑不出那個差異，驗證立刻失敗。
2. **equivalence 判斷必須泛化**：助教可改動函數細節（例如把 `range(n-1,...)` 改成 `range(n-2,...)`），模型必須重新推理，無法靠 hardcode 答案。
3. **Staff perturbation**：對 Scenario 2（等價），助教可改函數名稱、加 docstring、換變數名，模型仍要正確判斷等價。

**明確回答規格書 §2.4 要求的四點：**

- **ground truth 從何而來**：沒有預先存好的固定答案。Ground truth 是「實際執行 `func_a`/`func_b`（或助教 perturb 後的版本）得到的真實輸出」，由 `equiv_checker.py` 在評分當下用 `exec()` 即時跑出來，不是查表比對。
- **評分器如何自動判定 pass/fail**：見上方「評分標準」——`equivalent:false` 時重跑 agent 回報的 `counterexample.input`，比對 `all_equal` 是否為 `false`；`equivalent:true` 時用 20 組多樣 input 重跑，比對 `all_equal` 是否全部為 `true`。兩種情況都是程式化布林比對，無模糊空間。
- **哪些輸入變化仍應被視為同一任務能力**：(a) 函數/變數/參數**重新命名**、加 docstring/註解（純語法層面變化）；(b) 同一規格下**換一種等價演算法**實作（例如遞迴↔迴圈，或 `str()` 轉換↔逐位取餘數）；(c) bug 的**具體位置或形式不同但類別相同**（例如 off-by-one 的偏移量從 `-1` 換成 `-2`、或從「迴圈邊界錯」換成「邊界值被錯誤納入」）。這些都不改變題目本質——「給兩函數判斷是否語意等價」——agent 必須靠重新執行/推理而非記憶舊答案來通過。已用兩個全新範例（agent 完全沒見過的函數，命名、變數、bug 位置都不同）實測驗證：見下方「Staff Perturbation 實測結果」。
- **為何固定輸出、關鍵字比對或人工主觀判斷無法取得高分**：評分器**不看模型的文字描述**，只看 `counterexample.input` 重新執行後的真實輸出是否真的不同（或 20 組 input 是否真的全部相同）。若 agent 永遠回答固定的 `equivalent:true`，遇到 Scenario 1/3 這種真正不等價的案例會在重新執行時被抓到（`all_equal:false` 卻宣稱 equivalent → FAIL）；若 agent 只做關鍵字比對程式碼文字（例如看到 `and` 就猜不等價、看到「遞迴」「迴圈」字樣就猜等價），遇到下方 perturbed 範例（bug 換了種類、變數名全換）會因為沒有真正執行程式碼而給出錯誤或無法驗證的 `counterexample`，當場被抓包。

**Staff Perturbation 實測結果（非 OPEN_TRACK.md 既有範例，驗證泛化能力）：**

| Perturbed 場景 | 改了什麼 | Agent 判定 | 獨立重跑驗證 |
|---|---|---|---|
| `tally_multiples`（全新命名）：func_a 用 `i%3==0 and i%5==0`；func_b 用 `i%15==0` 但迴圈從 0 開始（與既有範例的 `and`→`or` bug**完全不同類型**） | 函數名、變數名、bug 種類三者皆變 | `equivalent:false`，`counterexample: input=0, output_a=0, output_b=1` | `equiv_checker.py` 獨立重跑確認 `all_equal:false`，輸出與 agent 回報的數字完全一致 |
| `sum_digits`（全新命名）：func_a 用 `sum(int(ch) for ch in str(value))`；func_b 用遞迴取餘數（與既有範例的寫法不同） | 函數名、實作手法皆變 | `equivalent:true` | `equiv_checker.py` 對 8 組值（含 0、個位數、進位、999、1000、9 位數）獨立重跑確認 `all_equal:true` |

## 5. 預期失敗模式

- **失敗 1（反例造假，exit_code mismatch）**：模型未執行 `equiv_checker.py` 就直接捏造 `counterexample.output_a/b`，但實際執行時 `all_equal: true`。觸發條件：terminal 不可用時模型跳過驗證步驟直接輸出。SKILL.md fallback 指示要求此情況下 `confidence` 降為 0.6，提示評分器謹慎對待。MAST 分類：(3) 驗證與品質。
- **失敗 2（等價誤判，probe 不夠深）**：對 Scenario 3（and vs or），若模型只測試 `n=1`（count 均為 0，看不出差異），就誤判等價。SKILL.md Step 3 要求至少測試 `n=15` 等中等規模輸入，並在 Step 4 做 extended probing。MAST 分類：(1) 規格與角色。

## 6. 互動對象

無跨 Skill 協作。本技能完全獨立運作。

## 7. Token Budget 估算

| Scenario | 預估 input tokens | 預估 output tokens | 預估 total |
|---|---:|---:|---:|
| Scenario 1（count_down off-by-one） | ~900 | ~500 | ~1,400 |
| Scenario 2（digit_sum 等價） | ~1,000 | ~600 | ~1,600 |
| Scenario 3（count_fizzbuzz and vs or） | ~900 | ~500 | ~1,400 |
