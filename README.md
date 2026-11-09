# IRMCTCldSearcher 部署指引

独立检索 IRMCT Case Law Database（CLD）。只访问 `cld.irmct.org`。

仓库：<https://github.com/HuiwowICCSkills/IRMCTCldSearcher>（公开）。

## 1. 环境

Python 3.10+，依赖 `requests`、`beautifulsoup4`、`pypdf`；无需登录。

## 2. 安装

```powershell
git clone https://github.com/HuiwowICCSkills/IRMCTCldSearcher.git "$env:USERPROFILE\.codex\skills\IRMCTCldSearcher"
python -m pip install -r "$env:USERPROFILE\.codex\skills\IRMCTCldSearcher\requirements.txt"
```

## 3. 自检

```powershell
& "$env:USERPROFILE\.codex\skills\IRMCTCldSearcher\run.ps1" doctor
```

## 4. 使用

```powershell
$cld = "$env:USERPROFILE\.codex\skills\IRMCTCldSearcher\run.ps1"
& $cld search 'command responsibility' --limit 10 --out './cld.json'
& $cld fetch 1 --out './record.json' --text-out './record.txt'
```

## 5. 排错

| 现象 | 处理 |
| --- | --- |
| `homedata.json` 很大 | 首次加载约 2,600 条记录；缓存后复用 |
| 某条 extract 失败 | 保留 `extract_error`，不影响其他结果 |
| PDF 页文本为空 | 扫描件；`needs_ocr=true` |

## 6. 边界

CLD 是精选上诉摘录，不是全部审判记录；引用前回到判决 PDF 核对段号和上下文。

## 实测效果（2026-11-09）

以下命令与结果来自本机 `~/.codex/skills/IRMCTCldSearcher` 的实网运行；检索日期 2026-11-09（Asia/Shanghai），输出为该次运行实际返回的 JSON 报告。

```powershell
& .\run.ps1 search 'command responsibility' --limit 5
```

- 状态：`ok`；CLD 检索报告 `total = 10`；本次返回 5 条。
- 代表性结果：

| 题名 | 类型 / 日期 | 链接 |
| --- | --- | --- |
| HATEGEKIMANA Idelphonse — Decision on Referral — Referral \| Legal framework \| Command responsibility in Rwandan law | retrieved_metadata；2008-12-04 | https://cld.irmct.org/assets/filings/331-ICTR-00-55B-0081-HATEGEKIMANA-DECISION-ON-THE-PROSECUTION-S-APPEAL-AGAINST-DECISION-ON-REFFERAL-UNDER-RULE-11bis.pdf |
| HADŽIHASANOVIĆ et al. — Decision on Command Responsibility — Superior responsibility \| Superior-subordinate relationship \| Successor liability | retrieved_metadata；2003-07-16 | https://cld.irmct.org/assets/Uploads/full-text-dec/2003/03-07-16 Hadzihasanovic Decision on Command Responsibility.pdf |
| HADŽIHASANOVIĆ et al. — Decision on Command Responsibility — Superior responsibility \| Applicability in non-international armed conflict | retrieved_metadata；2003-07-16 | https://cld.irmct.org/assets/Uploads/full-text-dec/2003/03-07-16 Hadzihasanovic Decision on Command Responsibility.pdf |

> 说明：`total = 10` 是 CLD 对该词的命中条数，检索范围为 `scope` 所述的 “curated appellate extracts across ICTY, ICTR and IRMCT”；本次返回 5 条，其中 4 条来自同一份 HADŽIHASANOVIĆ 裁定下的不同法律要点。返回项是 CLD 的**curated extract（编辑精选摘录）加元数据**，`content_scope` 写明它“not a complete trial record and not the judgment PDF itself”：`extract_text` 只是摘录段落，段号与脚注必须回到链接的 PDF 核对。链接指向该裁定/文书的 PDF，不是完整审判卷宗，也不能据此推断庭审全貌。
