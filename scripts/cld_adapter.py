#!/usr/bin/env python3
"""IRMCT Case Law Database adapter for IRMCTCldSearcher."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from skillkit import HTTP, RetrievalError, clean, pdf_pages, result, snippet

PROG = "cld_search.py"
DESCRIPTION = "Search the IRMCT Case Law Database (CLD)."
CACHE_DEFAULT = ".cld-cache"
FETCH_TIMEOUT_DEFAULT = 300

ROOT = "https://cld.irmct.org/"
HOMEDATA = "https://cld.irmct.org/assets/homedata.json"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/155.0.0.0 Safari/537.36"
)


def _headers() -> dict[str, str]:
    return {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"}


def make_http(args: argparse.Namespace) -> HTTP:
    return HTTP(
        args.cache,
        offline=args.offline,
        ttl=args.cache_ttl,
        timeout=args.timeout,
        user_agent=UA,
    )


def add_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=10, help="1..50 (default 10)")
    parser.add_argument("--offset", type=int, default=0, help=">= 0 (default 0)")
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Skip fetching each selected record's curated extract",
    )


def add_fetch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--text-out", help="Write extracted text here")


def _row_title(row: list[Any]) -> str:
    return f"{row[2]} — {row[3]} — {row[1]}"


def _record_url(row: list[Any]) -> str:
    return urljoin(ROOT, str(row[12])) if len(row) > 12 and row[12] else ROOT


def search(query: str, args: argparse.Namespace, http: HTTP) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("A non-empty query is required")
    if not 1 <= args.limit <= 50:
        raise ValueError("limit must be 1..50")
    if args.offset < 0:
        raise ValueError("offset must be >= 0")
    data, meta = http.json(HOMEDATA, headers=_headers())
    rows = data.get("data")
    if not isinstance(rows, list):
        raise RetrievalError("CLD homedata.json schema changed: no data array")
    query_norm = query.casefold()
    hits = [
        row
        for row in rows
        if isinstance(row, list)
        and query_norm in " ".join(str(value or "") for value in row[1:12]).casefold()
    ]
    hits.sort(key=lambda row: str(row[4]), reverse=True)
    selected = hits[args.offset : args.offset + args.limit]
    output: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in selected:
        record_id = str(row[0])
        extract_url = ROOT + "home/jsonExtract/" + record_id
        body = ""
        extract_error = None
        if not args.no_extract:
            try:
                payload, extract_meta = http.json(extract_url, headers=_headers())
                body = clean(payload.get("extract", ""))
            except RetrievalError as exc:
                extract_error = str(exc)
                warnings.append(f"record {record_id}: {extract_error}")
        output.append(
            result(
                _row_title(row),
                _record_url(row),
                "irmct-cld-json",
                snippet(body, query),
                id=record_id,
                date=row[4],
                notions=row[1],
                extract_url=extract_url,
                extract_text=body,
                extract_error=extract_error,
                access="official curated appellate extract; verify footnotes in the judgment PDF",
                content_scope=(
                    "CLD curated extract text and metadata; not a complete trial record "
                    "and not the judgment PDF itself"
                ),
            )
        )
    total = len(hits)
    return {
        "status": "ok" if output or total == 0 else "no-results-in-queried-index",
        "query": query,
        "total": total,
        "results": output,
        "pagination": {
            "offset": args.offset,
            "limit": args.limit,
            "next_offset": args.offset + len(output) if output and args.offset + len(output) < total else None,
        },
        "warnings": warnings,
        "scope": "IRMCT Case Law Database: curated appellate extracts across ICTY, ICTR and IRMCT",
        "evidence": http.evidence,
        "retrieved_at": meta.get("retrieved_at"),
    }


def fetch(locator: str, args: argparse.Namespace, http: HTTP) -> dict[str, Any]:
    if re.fullmatch(r"\d+", locator.strip()):
        url = ROOT + "home/jsonExtract/" + locator.strip()
    else:
        parsed = urlparse(locator)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() != "cld.irmct.org":
            raise ValueError("fetch expects a CLD record id or https://cld.irmct.org/ URL")
        url = locator
    body, meta = http.get(url, headers=_headers())
    if body.startswith(b"%PDF"):
        pages = pdf_pages(body)
        text = "\n\n".join(f"@@PAGE {p['page']}@@\n{p['text']}" for p in pages)
        if args.text_out:
            Path(args.text_out).write_text(text, encoding="utf-8")
        return {
            "status": "ok",
            "url": meta["source_url"],
            "pages": len(pages),
            "needs_ocr": not any(p["text"].strip() for p in pages),
            "page_text": pages,
            "text_out": str(Path(args.text_out).resolve()) if args.text_out else None,
            "sha256": meta["sha256"],
            "retrieved_at": meta["retrieved_at"],
        }
    if "json" in meta["content_type"].lower():
        payload = json.loads(body)
        extract = clean(payload.get("extract", ""))
        if args.text_out:
            Path(args.text_out).write_text(extract, encoding="utf-8")
        return {
            "status": "ok",
            "url": meta["source_url"],
            "text": extract,
            "text_characters": len(extract),
            "data": payload,
            "text_out": str(Path(args.text_out).resolve()) if args.text_out else None,
            "sha256": meta["sha256"],
            "retrieved_at": meta["retrieved_at"],
        }
    soup = BeautifulSoup(body, "html.parser")
    container = soup.select_one("main") or soup.body or soup
    for node in container.select("script, style, nav, header, footer, input, select, button, textarea, noscript"):
        node.decompose()
    text = container.get_text("\n", strip=True)
    if len(text) < 100:
        raise RetrievalError("Insufficient CLD page text")
    if args.text_out:
        Path(args.text_out).write_text(text, encoding="utf-8")
    return {
        "status": "ok",
        "url": meta["source_url"],
        "text": text,
        "text_characters": len(text),
        "text_out": str(Path(args.text_out).resolve()) if args.text_out else None,
        "sha256": meta["sha256"],
        "retrieved_at": meta["retrieved_at"],
    }


def doctor(args: argparse.Namespace) -> dict[str, Any]:
    checks = [
        {"check": "python", "ok": True, "detail": "Python runtime available"},
        {"check": "requests", "ok": True, "detail": "requests importable"},
        {"check": "beautifulsoup4", "ok": True, "detail": "bs4 importable"},
    ]
    if args.no_probe:
        return {"ok": True, "status": "ok (probes skipped)", "checks": checks}
    http = make_http(args)
    try:
        data, meta = http.json(HOMEDATA, headers=_headers())
        rows = data.get("data")
        checks.append(
            {
                "check": "CLD homedata",
                "ok": isinstance(rows, list),
                "rows": len(rows) if isinstance(rows, list) else None,
                "http_status": meta["http_status"],
                "bytes": meta["bytes"],
            }
        )
        ok = isinstance(rows, list) and bool(rows)
        if ok:
            first = rows[0]
            payload, extract_meta = http.json(
                ROOT + "home/jsonExtract/" + str(first[0]), headers=_headers()
            )
            checks.append(
                {
                    "check": "CLD extract",
                    "ok": bool(payload.get("extract")),
                    "http_status": extract_meta["http_status"],
                }
            )
            ok = bool(payload.get("extract"))
    except Exception as exc:
        checks.append({"check": "CLD probe", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        ok = False
    return {"ok": ok, "status": "ok" if ok else "error", "checks": checks, "catalog": {"home": HOMEDATA}}
