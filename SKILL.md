---
name: IRMCTCldSearcher
description: 独立检索 IRMCT Case Law Database（CLD），按主题、案件名或文书类型查找 ICTY/ICTR/IRMCT 的精选上诉分庭摘录，并读取每条记录的 curated extract。
---

# IRMCTCldSearcher

> **`<skill-dir>`** = 本 SKILL.md 所在目录。核心脚本为 `<skill-dir>/scripts/cld_search.py`；Windows 用 `<skill-dir>/run.ps1`，macOS/Linux 用 `<skill-dir>/run.sh`。部署与排错见 [README.md](README.md)。

这个 skill 只做 `cld.irmct.org` 一个站点：

- `search`：读取公开 `assets/homedata.json`，按 `notions`、案件名、文书类型和日期过滤；默认再读取每条选中记录的 `jsonExtract/<id>`；
- `fetch`：按记录 id 或 `jsonExtract` URL 读取 curated extract；也支持 CLD 上的 PDF 链接；
- `doctor`：探测 homedata 和第一条 extract。

## 命令

```powershell
& '<skill-dir>/run.ps1' search 'command responsibility' --limit 10 --out './cld-search.json'
& '<skill-dir>/run.ps1' search 'genocide' --limit 5 --no-extract

# 站点自身的 Advanced Search：全文 + Notion + 案件 + 文书类型 + 日期 + 法庭
& '<skill-dir>/run.ps1' search 'command responsibility' --mode advanced --notion 'Superior responsibility' --tribunal ICTY --date-from 2010-01-01 --date-to 2020-12-31 --limit 10

& '<skill-dir>/run.ps1' fetch 1 --out './cld-record.json' --text-out './cld-record.txt'
& '<skill-dir>/run.ps1' doctor
```

通用参数：`--out`、`--cache`、`--cache-ttl`、`--offline`、`--timeout`。`search` 另有 `--limit`（1..50）、`--offset`、`--no-extract`；`fetch` 另有 `--text-out`。

## 结果边界

- CLD 是**精选上诉分庭摘录**，不是全部审判记录，也不是完整判决 PDF；`extract_text` 是 CLD 编辑后的摘录，引用前必须回到判决 PDF 核对段号和上下文。
- `homedata.json` 是全量公开索引；`total` 是本地过滤后的命中数，不是全库记录数。
- `--mode advanced` 调用 `https://cld.irmct.org/advanced-search/` 的服务端检索：`keyword` 检索摘录正文，`--notion`、`--case`、`--filing`、`--tribunal` 和日期范围是站点自身的分面；它比本地 `homedata.json` 过滤覆盖更多正文命中。`--notion` 可重复；标签按站点下拉框解析，大小写不敏感。
- Advanced Search 每页 20 条，`total` 来自页面 `Showing N results`；返回的 `filing_url` 是判决 PDF，`case_url` 是案件页。高级模式不读取 `jsonExtract`，因为服务端返回的已经是摘录正文。
- `fetch` 的 PDF 页文本页号是 PDF 位置，不是印刷页码；扫描件可能 `needs_ocr=true`。
- CLD 的摘要可能省略脚注、反对意见和前后文；不要仅凭 `extract` 断言法院完整推理。

## 参考

- 2026-11-09 实测：`homedata.json` 结构、`jsonExtract` 字段与 PDF 链接：[references/cld-search.md](references/cld-search.md)
- 部署、环境与排错：[README.md](README.md)
