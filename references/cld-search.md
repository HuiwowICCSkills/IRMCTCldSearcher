# IRMCT CLD 检索实测记录（2026-11-09）

## 数据端点

- 全量索引：`https://cld.irmct.org/assets/homedata.json`（约 686 KB，2,580 条记录）
- 单条摘录：`https://cld.irmct.org/home/jsonExtract/<id>`

`homedata.json` 行结构（实测）：

`[id, notions, case_name, document_type, date, ..., relative_path]`

示例：`[1, "Conspiracy to commit genocide | Mens rea", "POPOVIĆ et al.", "Appeal Judgement", "2015-01-30", ..., "assets/filings/Judgement-Popovic-reduced.pdf"]`

## 实测

- `command responsibility --limit 2` → `status=ok`、`total=10`，前两条为 HATEGEKIMANA / HADŽIHASANOVIĆ 记录
- `jsonExtract/1` → `{"extract":"<p class=\"Quotes\">529. [...]"}`，811 字节
- 第一条结果链接 PDF → 19 页、`needs_ocr=false`

## 解析

- 标题：`case_name — document_type — notions`
- 日期：`row[4]`
- extract：`jsonExtract/<id>` 的 `extract` HTML，需去标签
- 结果 URL：`urljoin("https://cld.irmct.org/", row[12])`

## 边界

CLD 是精选上诉摘录，不是全部审判记录；引用前回到判决 PDF 核对段号、脚注和上下文。
