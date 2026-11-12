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

## 实测效果（2026-11-12）

以下命令与结果来自本机 `~/.codex/skills/IRMCTCldSearcher` 的实网运行；检索日期 2026-11-12（Asia/Shanghai），输出为该次运行实际返回的 JSON 报告。

```powershell
$cld = "$env:USERPROFILE\.codex\skills\IRMCTCldSearcher\run.ps1"
& $cld search 'command responsibility' --mode advanced --limit 5
```

- 状态：`ok`；CLD 页面报告 `Showing 59 results`；本次返回 5 条。
- 模式：`advanced`，使用 CLD 自身的 `/advanced-search/` 服务端检索，不是 `homedata.json` 本地过滤。
- 代表性结果：

| 案件 / 文书 | 文书日期 | PDF |
| --- | --- | --- |
| MLADIĆ Ratko (MICT-13-56-A) — Appeal Judgement | 08.06.2021 | https://cld.irmct.org/assets/filings/Mladic-AJ-public-redacted-version.pdf |
| TURINABO, Maximilien (MICT-18-116-PT) — Decision on Prosecution Appeal of Decision on Challenges to Jurisdiction | 28.06.2019 | https://cld.irmct.org/assets/filings/Decision-on-challenges-to-jurisdiction-contempt2.pdf |
| KARADŽIĆ Radovan (MICT-13-55-A) — Appeal Judgement | 19.03.2019 | https://cld.irmct.org/assets/filings/2019.03.20-Karadzic-Appeal-Judgement.pdf |

> 说明：CLD 返回的是**精选上诉分庭摘录（curated extract）**，不是完整审判记录，也不是完整判决 PDF。`total=59` 是高级检索页的结果数；引用前必须回到 `filing_url` 的 PDF 核对段号、脚注和上下文。
