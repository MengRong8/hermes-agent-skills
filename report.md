# 期末報告 — AIASE 2026 Final Project

> 學生: MengRong8 / GitHub: `MengRong8`

---

## 1. 設計決策

### 1.1 Basic — Text2SQL Skill

**SKILL.md 設計**：選擇將 SQL 模式判斷（DISTINCT vs 無 DISTINCT、INNER JOIN vs LEFT JOIN、HAVING、NOT IN 等）整理成 Cheatsheet 表格，而非只給自然語言描述。原因是 LLM 在看到表格時能快速查閱邊界條件，實測下來對 LEFT JOIN 的誤判（漏掉零計數列）與 DISTINCT 遺漏有明顯改善。

**validate_sql.py harness**：用 `sqlite3.connect(":memory:") → executescript(schema_ddl) → EXPLAIN <sql>` 的方式做語法與 schema grounding 驗證。`EXPLAIN` 不需要資料就能解析欄位名稱，能擋住「引用不存在欄位」這類低級錯誤，同時拒絕 CTE / window function / DDL（規格書禁用）。**擋不住語意錯誤**（例如少 DISTINCT、JOIN 方向錯）——這類錯誤只能靠評分環境的 hidden DB 才能裁定，harness 不試圖偽裝能做到。

**信心分數**：validate 通過設 0.7–0.9，validation 失敗後最多重試 3 次，仍失敗時設 0.3 並直接送出，而非棄答。這讓評分器至少能執行一個 SQL，有機會拿部分分數。

### 1.2 Pairwise — Code Author & Bug Hunter

**Code Author**：重點在 selftest.py harness。LLM 寫完程式碼後，harness 用 `exec()` 在沙盒內執行 sample_tests，回傳 passed/failed/errors。這讓模型能在發現測試失敗時自我修正（最多 3 輪），不依賴模型自己判斷「這段 code 是否正確」。禁用的 import 透過 AST 靜態掃描，不用 try/except 捕捉執行期錯誤。**SLOC 限制**用 `radon raw <file> --json` 的 `sloc` 欄位（規格書 §2.3 指定方式）。**效能限制**（5s/test timeout、規格書 §2.3）原本只有 SLOC 檢查、沒有計時，後補上：每個 sample test 計時，超過 2 秒（比評分用的 5 秒更嚴格，留安全邊界）視為失敗並提示「可能是 O(n²)/O(n³) 等複雜度問題」；考慮到 `signal.SIGALRM` 是 POSIX-only（Windows 開發環境不會真的中斷執行），額外加了一道「執行完後檢查 elapsed_sec 是否超標」的事後判定，確保本機 Windows 測試也抓得到慢演算法，不只靠 POSIX 評分環境的強制中斷。同時新增 `slow_warning`（0.5–2 秒視為高風險訊號），SKILL.md 也補上輸入規模/Big-O 評估的步驟與 Pitfalls 條目。已用 O(n³) 測試函式與既有 5 個 reference task 驗證：慢演算法被攔截為失敗、原有測試全部仍 5/5 通過。

**Bug Hunter**：採三層決策樹：Level A（動態 crash 證據）→ Level B（靜態分析確定違反 spec）→ Level C（僅有懷疑，不報告）。這個設計是為了壓低誤報率——clean code 判錯成 buggy 有額外懲罰（佔 25% 分數），所以寧願漏報也不要誤報。analyze.py harness 對 edge inputs 動態探測，提供 crash line number 讓 Level A 決策有確鑿證據。

---

## 2. 實際遭遇之失敗與分析

### 失敗 1 — Windows bash 路徑不相容導致所有 terminal 指令失敗

- **觸發場景**：在 Windows 上執行 `python run_dev.py`，Hermes 啟動 local terminal（`/bin/bash`），嘗試執行 `python skills/text2sql-MengRong8/scripts/validate_sql.py`。
- **log 片段**：
  ```
  /bin/bash: line 1: cd: <project-root>: No such file or directory
  exit_code: 126
  ```
- **成因分析**：Hermes 在每個 terminal 指令前自動加上 `cd <cwd>` 作為第一行。Python 的 `os.getcwd()` 在 Windows 上回傳反斜線格式（`<drive>:\\<path>`），Hermes 直接把這個字串傳給 bash。bash（Git Bash）不認識 Windows 反斜線路徑，cd 失敗，而 `&&` 運算子讓後續指令也跳過，導致 `exit_code: 126`，**所有指令都無法執行**。
- **修正方式**：
  1. 在 SKILL.md 加入明確的 fallback 指示：terminal 完全失效時，模型直接在 stdout 輸出 fenced JSON block，不再嘗試 terminal。
  2. 在 `run_dev.py` 加入 `_parse_result_from_stdout()` 備援：當檔案讀取失敗，改從 hermes stdout 解析 JSON。
  3. 擴充備援 parser 支援 ```sql``` block：當模型只輸出 SQL 而非完整 JSON 時，自動組出最小 result dict。
- **MAST 分類**：(3) 驗證與品質 — 環境探測失敗導致 agent 誤判執行狀態

---

### 失敗 2 — 模型在 terminal 錯誤後拒絕繼續輸出結果

- **觸發場景**：SKILL.md 已告知「看到 cd 錯誤請忽略繼續執行」，但模型在 exit_code 126 後選擇回報「無法繼續」，不輸出任何 JSON。
- **log 片段**：
  ```
  I am unable to complete the task as intended due to persistent issues with the `terminal` tool.
  All attempts to execute Python scripts (e.g., `validate_sql.py`, `run.py`) within the `terminal`
  result in an `exit_code: 126` ...
  ```
- **成因分析**：原本的 SKILL.md 只說「看到 cd 錯誤忽略它，繼續看後面的輸出」，但 exit_code 126 表示指令根本沒跑（不是跑完有 cd 錯誤再跑），模型正確判斷「沒有輸出可以看」，因此遵循 SKILL.md 的話仍然放棄。指示的假設與實際環境不符。
- **修正方式**：更新 SKILL.md fallback 指示，明確區分「有輸出但帶 cd 錯誤」vs「exit_code 126 完全沒輸出」，後者直接要求模型輸出 JSON 到 response，不再嘗試任何 terminal 指令。
- **MAST 分類**：(1) 規格與角色 — SKILL.md 的指示對環境狀態的描述不夠精確

---

### 失敗 3 — liteLLM gateway MidStreamFallbackError

- **觸發場景**：使用課程 aiase provider（`HERMES_PROVIDER=aiase`）執行 basic track 測試，運行約 400 秒後失敗。
- **log 片段**：
  ```
  API call failed after 1 retries: HTTP 500: litellm.MidStreamFallbackError:
  litellm.APIConnectionError: APIConnectionError:
  Hosted_vllmException - Timeout on reading data from socket.
  Received Model Group=aiase_model
  ```
- **成因分析**：課程 liteLLM gateway 在 streaming 模式下，socket 在約 65 秒後被伺服器切斷（推測為伺服器端 read timeout 或尖峰時段負載過高）。Hermes 的 `api_max_retries: 3` 讓整個流程耗費 ~1200 秒才報錯。
- **修正方式**：
  1. 將 `api_max_retries` 從 3 降為 1，讓失敗快速顯現（~400s → ~130s）。
  2. 移除 terminal toolset（`HERMES_TOOLSETS=skills`），降低模型生成長度，減少 socket 存活時間需求。
  3. 本地反覆迭代時改選 `aiase` 底下的 `gemini-2.5-flash` 模型（`docs/hermes-config.example.yaml` 列出的官方選項之一，仍是同一個 `aiase` LiteLLM gateway、同一組課程 token，只是後端模型不同），避開 `gemma4` 後端（`Hosted_vllmException` 顯示是其自架 vLLM serving 不穩定，並非 gateway 本身的問題）；最終驗證仍交叉測試兩個模型。
- **MAST 分類**：(2) agent 間協調 — LLM API provider 的不穩定影響整個 pipeline 的可靠性

---

### 失敗 4 — Code Author 自測未涵蓋空輸入導致 Bug Hunter 誤判

- **觸發場景**：Code Author Skill 產生如下結果（task_042，merge_intervals 題目）：
  ```json
  {
    "task_id": "task_042",
    "code": "from typing import List\ndef merge_intervals(intervals):\n    intervals.sort(key=lambda x: x[0])\n    merged = [intervals[0]]\n    for cur in intervals[1:]:\n        if cur[0] <= merged[-1][1]:\n            merged[-1][1] = max(merged[-1][1], cur[1])\n        else:\n            merged.append(cur)\n    return merged",
    "loc": 9,
    "self_test_results": {"passed": 1, "failed": 0},
    "rationale": "Sort then sweep.",
    "confidence": 0.85
  }
  ```
  `self_test_results` 顯示 passed: 1, failed: 0，模型自信心 0.85，但傳入 `[]` 時會在 `intervals[0]` 拋出 `IndexError`。
- **成因分析**：selftest.py harness 執行的是 SKILL.md 中提供的 `sample_tests`，這些測試只涵蓋正常輸入（如 `[[1,3],[2,6]]`）。LLM 沒有主動加入 edge case（空串列、單元素串列、全部重疊），而 harness 也沒有強制要求探測邊界條件。結果是 self_test_results 全過，但空輸入仍會 crash。Bug Hunter 若信任 `confidence: 0.85`，會在 clean/buggy 判別上傾向低估 bug 嚴重性。
- **修正方向**：
  1. 在 selftest.py 加入自動邊界測試：空串列（`[]`）、單元素（`[[1,5]]`）、全部不重疊、全部包含，模型必須通過這些才能設 confidence > 0.8。
  2. SKILL.md 加入 edge case checklist，明確要求 Author 自行補充邊界測試。
- **MAST 分類**：(3) 驗證與品質 — selftest harness 的覆蓋範圍不足，產生錯誤的 confidence 信號

---

### 失敗 5 — Bug Hunter 在不同模型間因 `line_start`/`type` 一字之差全錯

- **觸發場景**：`task_pair_003`（`parse_csv_line`，`buggy_code` 在 `for c in line:` 迴圈內完全沒有引號處理）。Ground truth（`dev_set/pairwise/reference_tasks/task_pair_003.json` 的 `bugs_in_buggy`）標記：
  ```json
  {"line_start": 5, "type": "unhandled_input", "severity": "high", ...}
  ```
  用 `gemini-2.5-flash` 測試時，模型正確抓到「沒有處理 quoted field」這個語意，但實際回報（`dev_run_results/result_task_pair_003_buggy.json`）是：
  ```json
  {"line_start": 4, "type": "logic_error", ...}
  ```
  `line_start` 指到迴圈本身的 `for` 那行（gold 是迴圈內的 `if c == ',':`），`type` 也從 `unhandled_input` 變成 `logic_error`。`_bug_set_from_obj` 把兩者轉成 `(line_start, type)` tuple 比對，兩個欄位都不一致 → 完全不命中。
- **log 片段（修正前，`run_dev.py` 實際輸出）**：`dev_run_results/pairwise_bug-hunter_bug-hunter-MengRong8_20260616_121923.json`
  ```json
  {
    "task_id": "task_pair_003",
    "passed": false,
    "reason": "recall=0.00, clean_fp=0",
    "elapsed_sec": 40.73,
    "extras": {"jaccard": 0.0, "recall_like": 0.0, "clean_fp": 0}
  }
  ```
- **log 片段（修正後，`run_dev.py` 實際輸出）**：`dev_run_results/pairwise_bug-hunter_bug-hunter-MengRong8_20260616_123636.json`
  ```json
  {
    "task_id": "task_pair_003",
    "passed": true,
    "reason": "",
    "elapsed_sec": 141.05,
    "extras": {"jaccard": 1.0, "recall_like": 1.0, "clean_fp": 0}
  }
  ```
- **成因分析**：`_bug_set_from_obj` 把每個回報的 bug 轉成 `(line_start, type)` 的精確 tuple 做 Jaccard/recall 比對，不容許行號或 type 任一欄位有誤差。SKILL.md 原本只用抽象文字描述「指向 if 而非 for」「`unhandled_input` vs `logic_error` 的差異」，模型對「整個迴圈邏輯都沒處理 quoting」這句話的理解不同——有的模型認為迴圈本身（`for` 那行）就是問題起點，且因為程式碼確實有在「做事」（只是邏輯不對），歸類為 `logic_error` 也並非不合理，只是跟 ground truth 的標記慣例（完全沒有對應處理 → `unhandled_input`；標在最內層該分支判斷的行 → `line_start`）不同。
- **修正方式**：在 SKILL.md Step 5 加入一個具體的、附行號標註的 worked example（迴圈包 if/else，缺漏的判斷藏在 if 而非 for），明確示範「即使整段迴圈都要重寫，`line_start` 仍要標在最內層、真正該分支判斷的那一行」；並在 Pitfalls 表中加入 `logic_error` vs `unhandled_input` 的判斷準則（規格完全沒有對應處理時用 `unhandled_input`，程式有嘗試處理但邏輯錯誤時才用 `logic_error`）。加入後重測，`gemini-2.5-flash` 穩定通過 `task_pair_003`（見上方修正後 log，`jaccard=1.0`）。
- **MAST 分類**：(3) 驗證與品質 — 精確行號/type 比對的評分設計對模型間的合理推理差異過度敏感，靠 SKILL.md 範例與分類準則校準，而非放寬比對邏輯（比對邏輯為評分公式本身，不可更動）。

---

## 3. 改進方向

1. **Terminal 環境隔離**：SKILL.md 中的腳本呼叫改為用 Python `-c` inline 方式執行，完全避開 bash cd 問題。例如 `python -c "import sys; sys.path.insert(0, 'skills/text2sql-MengRong8/scripts'); import validate_sql; ..."`。

2. **Stdout 解析標準化**：目前 fallback 是用 regex 找 fenced JSON block，脆弱（換行格式改變就失效）。改用 JSON 的大括號深度計數器找最外層 object，更穩健。

3. **Bug Hunter 動態探測強化**：analyze.py 目前只用 `exec()` 執行 edge inputs。對 off-by-one 類型的 bug（例如 `<` vs `<=`）無法透過 crash 偵測，應加入對比測試（clean_code vs buggy_code 對同一組 input 的輸出差異）。

4. **信心分數校準**：目前 fallback JSON 的 confidence 固定為 0.5–0.7，沒有根據 self_test_results 動態調整。應在 stdout 備援解析後，根據實際測試通過率重新計算信心分數。

---

## 4. 分工（僅兩人組需填）

> 本專案為個人作業，無需填寫分工。

---

## 5. 引用說明

- **run_dev.py**：基於課程提供的 starter 版本，**比對答案與驅動 agent 的核心邏輯（`extract_last_json_block`、`bag_equal`、`is_read_only_sql`、`run_sql`、`_bug_set_from_obj` 及 Jaccard/recall 計算）完全未修改**，僅加入以下不影響評分結果的輔助功能：
  - `call_hermes_skill`：新增 `HERMES_PROVIDER` / `HERMES_MODEL` 環境變數，本地測試時用來在課程 `aiase` LiteLLM gateway 底下切換 `gemma4` / `gemini-2.5-flash` 兩個官方提供的模型（皆為 `docs/hermes-config.example.yaml` 列出的選項，同一個 provider、同一組課程 token，未使用任何外部 API）做跨模型交叉驗證，呼應規格書「model-agnostic，評分模型為 held-out」的要求；`subprocess.run` 明確指定 `encoding='utf-8', errors='replace'`，修正 Windows 中文 locale（cp950）下讀取 hermes UTF-8 輸出會 crash 的問題（Linux 評分環境本身即為 UTF-8，此修改在該環境下無作用）
  - `grade_basic` / `grade_pairwise`：新增 `--task` / `--limit` 參數，可只跑單一題目或前 N 題以節省自測時的 token 額度，不影響評分公式
  - JSON 解析失敗時新增 debug dump（寫入 `dev_run_results/debug_stdout_<task_id>.txt`），純粹方便除錯
  - `_print_summary` / `_check_only`：把 `✓`/`✗` 改成 `PASS`/`FAIL`、`OK`/`NG` 純文字，修正 Windows cp950 終端機印出 Unicode 符號會 crash 的問題，純顯示用途
- **SKILL.md 設計**：SQL Pattern Cheatsheet 的 NOT IN / universal quantifier 例子參考自 SQL 教學文件，自行改寫為 SQLite 方言。
