# IRMCTCldSearcher 部署指引

独立检索 IRMCT Case Law Database（CLD）。只访问 `cld.irmct.org`。

仓库：<https://github.com/GDUFSICCSkills/IRMCTCldSearcher>（私有）。

## 1. 环境

Python 3.10+，依赖 `requests`、`beautifulsoup4`、`pypdf`；无需登录。

## 2. 安装

```powershell
git clone https://github.com/GDUFSICCSkills/IRMCTCldSearcher.git "$env:USERPROFILE\.codex\skills\IRMCTCldSearcher"
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
