# PAIRWISE_ROLE 宣告

> Pairwise Track：**兩個角色（Code Author + Bug Hunter）都已實作並提交**。
> 評分時，課程會以固定 random seed **隨機抽取其中一個角色**評分，並與另一位同學隨機配對的對向角色；
> 抽取結果、配對清單與每次執行 log 皆會保存供查核。下方 `roles:` 區塊依規格書 §2.3 指定格式宣告。

```yaml
roles:
  - role: code-author
    skill_path: skills/code-author-MengRong8/
  - role: bug-hunter
    skill_path: skills/bug-hunter-MengRong8/
```

## 規則

1. `roles` 必須同時包含 `code-author` 與 `bug-hunter` 兩筆，且不可重複 — 上方已滿足。
2. 每個 `skill_path` 必須指向實際存在、且能被 `hermes skills list` 看到的 skill 資料夾。
3. 評分時課程會以固定 random seed 隨機抽取其中一個角色評分，並與另一位同學隨機配對；無法選擇被抽到哪個角色，也無法選擇配對對象。
4. 若本檔案缺漏、格式錯誤、未同時宣告兩個角色，或任一 `skill_path` 不存在 / 無法被載入，Pairwise Track 視為無法評分，該 Track 0 分。

## 備註

兩個角色皆已實作完成：`skills/code-author-MengRong8/`（含 selftest.py harness，LLM 寫完程式碼後
用 `exec()` 跑 sample_tests 自我修正）與 `skills/bug-hunter-MengRong8/`（含 analyze.py harness，
動態探測 edge inputs 取得 crash line number 作為高信心證據）。已用 `run_dev.py` 對兩者跑過
本地 dev_set 自測，並在課程官方 `aiase` LiteLLM gateway 下交叉測試 `gemma4` 與 `gemini-2.5-flash`
兩個官方提供的模型（皆為 `docs/hermes-config.example.yaml` 列出的選項，同一個 gateway、同一組
課程 token，未使用任何外部 API）皆可通過，驗證 skill 不依賴單一模型的脾氣。
