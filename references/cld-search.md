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

## Advanced Search（2026-11-12 浏览器核对）

页面：`https://cld.irmct.org/advanced-search/`，服务端 GET 表单，不需要 JavaScript。

参数：

| 参数 | 含义 | 备注 |
| --- | --- | --- |
| `keyword` | 摘录正文全文检索 | 与 `homedata.json` 的标题/notion 过滤不同 |
| `notion[]` | Notion 多选 | 站点下拉框有 1,138 个选项，值如 `2`、`1096` |
| `case` | 案件多选 | 158 个选项，值如 `1`、`107` |
| `filing` | 文书类型多选 | 549 个选项，值如 `5`、`563` |
| `from` / `to` | 日期范围 | 站点格式 `d-m-Y` |
| `tribunal` | 法庭 | `1`=ICTY，`2`=ICTR，`3`=IRMCT |
| `p` | 结果偏移 | 每页 20 条，`p=0,20,40…` |
| `action_search` | 提交按钮 | 固定 `Search` |

实测 `keyword=command responsibility` → `Showing 59 results (20 per page)`；`notion=Superior responsibility` + `tribunal=ICTY` + `2010-01-01..2020-12-31` → 4 条。结果是 `table.extract-table` 中的元数据行 + `td.nrb` 摘录行配对，不是每条一个 `div.extract-content`。
