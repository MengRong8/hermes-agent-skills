# Verifiable Agent Skills for Hermes Agent

> AIASE 2026（AI-Assisted Software Engineering）期末專案　｜　個人作業
> **專案總分 91.09**（Basic 29.0／30、Open Track 94.2／100）

LLM Agent 最大的問題不是「不會做」，而是「做錯了也不知道」。本專案在 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 上設計四個 Skill，每個 Skill 都搭配一支**可執行的驗證腳本（harness）**：模型產生答案後，由程式實際執行、檢查，再把結果回饋給模型自我修正。信心分數也依驗證結果決定，而不是由模型自評。

## 四個 Skill

| 軌道 | Skill | 任務 | 驗證機制 |
|---|---|---|---|
| Basic | [`text2sql`](skills/text2sql-MengRong8/) | 自然語言 → SQLite 查詢 | 在記憶體資料庫建立 schema 後執行 `EXPLAIN`，擋下不存在的欄位與禁用語法；失敗最多重試 3 次 |
| Pairwise | [`code-author`](skills/code-author-MengRong8/) | 依規格撰寫 Python 函式 | 沙盒執行測試案例、AST 掃描禁用 import、`radon` 量測 SLOC、逐題計時攔截高複雜度演算法 |
| Pairwise | [`bug-hunter`](skills/bug-hunter-MengRong8/) | 找出程式中的 bug 並標註行號與類型 | 對邊界輸入動態探測取得 crash 證據；三層決策（動態證據 → 靜態違反規格 → 僅懷疑則不報）以壓低誤報 |
| Open | [`open-equiv-check`](skills/open-equiv-check-MengRong8/) | 判斷兩個函式是否語意等價，不等價時給出反例 | `equiv_checker.py` 實際執行兩函式驗證反例；判定等價時以 20 組多樣輸入交叉驗證 |

Open Track 為自訂題目，設計說明與驗證情境見 [`OPEN_TRACK.md`](OPEN_TRACK.md)。

## 設計重點

- **驗證優先於自評**：每個 Skill 的輸出都必須通過 harness，信心分數由驗證結果決定。
- **誠實面對 harness 的極限**：例如 Text2SQL 的 `EXPLAIN` 只能擋語法與 schema 錯誤，擋不住少了 `DISTINCT` 這類語意錯誤，報告中明確寫出而不假裝能做到。
- **依評分的不對稱性設計策略**：Bug Hunter 把乾淨程式誤判為有 bug 會被額外扣分，因此寧可漏報也不誤報。
- **跨模型驗證**：在 `gemma4` 與 `gemini-2.5-flash` 兩個模型上交叉測試，確保 Skill 不依賴特定模型的行為。

## 失敗分析

[`report.md`](report.md) 記錄五個實際遇到的失敗，每個都附 log、成因分析、修正方式與 MAST 失敗分類。例如：

- Hermes 在 Windows 上把反斜線路徑傳給 bash，導致所有指令以 exit code 126 失敗 → 設計不依賴 terminal 的 JSON 輸出備援。
- Code Author 自測全過卻在空輸入 crash → 指出 harness 覆蓋率不足會產生錯誤的高信心訊號。
- Bug Hunter 因行號與 bug 類型標註慣例不同而完全不命中 → 以附行號的範例與分類準則校準模型，而非放寬比對邏輯。

## 使用方式

```bash
pip install -r requirements.txt
cp -r skills/* ~/.hermes/skills/
hermes chat --toolsets skills,terminal -q '/open-equiv-check-MengRong8 {"task_id":"t1","description":"count_down(n) returns [n, ..., 1]","func_a":"def count_down(n):\n    return list(range(n, 0, -1))","func_b":"def count_down(n):\n    return list(range(n-1, 0, -1))","entry":"count_down"}'
```

各 Skill 的輸入輸出格式見其 `SKILL.md`。

> 本 repo 只收錄我自己撰寫的 Skill 與報告；課程提供的 starter、測資、參考對手 Skill 與評分程式未收錄，因此 `test_local.py` 需搭配課程測資才能執行。
