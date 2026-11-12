#!/usr/bin/env python3
"""IRMCT Case Law Database adapter for IRMCTCldSearcher."""

from __future__ import annotations

import argparse
import datetime as dt
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
        "--mode",
        choices=("local", "advanced"),
        default="local",
        help=(
            "local: filter the public homedata.json index; "
            "advanced: use the CLD server-side advanced-search form (full text + facets)"
        ),
    )
    parser.add_argument(
        "--notion",
        action="append",
        default=[],
        help="Notion label or numeric id; repeatable (advanced mode)",
    )
    parser.add_argument("--case", help="Case name fragment or numeric id (advanced mode)")
    parser.add_argument("--filing", help="Filing label fragment or numeric id (advanced mode)")
    parser.add_argument("--tribunal", help="ICTY, ICTR, IRMCT, or 1/2/3 (advanced mode)")
    parser.add_argument("--date-from", dest="date_from", help="Start date YYYY-MM-DD (advanced mode)")
    parser.add_argument("--date-to", dest="date_to", help="End date YYYY-MM-DD (advanced mode)")
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


ADVANCED_URL = ROOT + "advanced-search/"
ADVANCED_PAGE_SIZE = 20


def _option_value(
    soup: BeautifulSoup, select_name: str, supplied: str | None
) -> str | None:
    """Resolve a numeric value or label fragment against a CLD select."""
    if not supplied:
        return None
    value = str(supplied).strip()
    if not value:
        return None
    select = soup.select_one(f'select[name="{select_name}"]')
    if select is None:
        return value
    options = [
        (str(option.get("value", "")), clean(option.get_text(" ", strip=True)))
        for option in select.select("option")
    ]
    if any(value == item_value for item_value, _ in options):
        return value
    needle = value.casefold()
    exact = [item_value for item_value, label in options if label.casefold() == needle]
    if exact:
        return exact[0]
    partial = [item_value for item_value, label in options if needle in label.casefold()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        if len(set(partial)) == 1:
            return partial[0]
        labels = [label for item_value, label in options if item_value in partial][:8]
        raise ValueError(
            f"{select_name} value {supplied!r} is ambiguous; candidates: "
            + "; ".join(labels)
        )
    raise ValueError(f"{select_name} has no option matching {supplied!r}")


def _cld_date(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            parsed = dt.datetime.strptime(text, fmt)
            return parsed.strftime("%d-%m-%Y")
        except ValueError:
            continue
    raise ValueError("CLD dates must be YYYY-MM-DD or DD-MM-YYYY")


def _advanced_params(soup: BeautifulSoup, query: str, args: argparse.Namespace, offset: int) -> dict[str, str]:
    params: dict[str, str] = {
        "keyword": query,
        "case": _option_value(soup, "case", args.case) or "",
        "filing": _option_value(soup, "filing", args.filing) or "",
        "from": _cld_date(args.date_from),
        "to": _cld_date(args.date_to),
        "tribunal": _option_value(soup, "tribunal", args.tribunal) or "",
        "action_search": "Search",
        "p": str(offset),
    }
    notions = [_option_value(soup, "notion[]", value) or "" for value in args.notion]
    params["notion[]"] = [value for value in notions if value]  # type: ignore[assignment]
    return params


def _parse_advanced_page(
    soup: BeautifulSoup, meta: dict[str, Any], query: str, limit: int, offset: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    text = soup.get_text(" ", strip=True)
    count_match = re.search(r"Showing\s+([\d,]+)\s+results?", text, re.I)
    if not count_match:
        if re.search(r"no results", text, re.I):
            return [], {"total": 0, "offset": offset, "limit": limit, "next_offset": None}
        raise RetrievalError(
            "CLD advanced search returned no result count; form error or schema change"
        )
    total = int(count_match.group(1).replace(",", ""))
    page_start = (offset // ADVANCED_PAGE_SIZE) * ADVANCED_PAGE_SIZE
    within = offset - page_start
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for tr in soup.select("div.extract-content table.extract-table tr"):
        cell_one = tr.select_one("td.cell-one")
        if cell_one:
            notions = [
                clean(anchor.get_text(" ", strip=True))
                for anchor in cell_one.select("ul.extract-notions li.notion-tag a")
            ]
            filing = tr.select_one("td.cell-two span.extract-info a[href]")
            case = tr.select_one("td.cell-tree a[href]")
            if not filing and not case:
                current = None
                continue
            filing_title = clean(filing.get_text(" ", strip=True)) if filing else ""
            case_title = clean(case.get_text(" ", strip=True)) if case else ""
            title = " — ".join(
                part for part in (case_title, filing_title, " | ".join(notions)) if part
            )
            current = {
                "title": title or filing_title or case_title,
                "url": (
                    urljoin(meta["source_url"], filing["href"])
                    if filing
                    else urljoin(meta["source_url"], case["href"])
                ),
                "notions": notions,
                "filing": filing_title,
                "filing_url": urljoin(meta["source_url"], filing["href"]) if filing else "",
                "case": case_title,
                "case_url": urljoin(meta["source_url"], case["href"]) if case else "",
                "body": "",
            }
            rows.append(current)
            continue
        if current is not None:
            excerpt = tr.select_one("td.nrb div.highlight-area")
            if excerpt is not None:
                current["body"] = clean(excerpt.get_text(" ", strip=True))
    for row in rows:
        row.update(
            result(
                row["title"],
                row["url"],
                "irmct-cld-advanced",
                snippet(row["body"], query),
                notions=row["notions"],
                filing=row["filing"],
                filing_url=row["filing_url"],
                case=row["case"],
                case_url=row["case_url"],
                extract_text=row["body"],
                access="CLD server-side advanced-search result; excerpt is a curated extract",
                content_scope=(
                    "CLD server-side full-text search result and curated excerpt; "
                    "verify the cited paragraph in the judgment PDF"
                ),
            )
        )
        row.pop("body", None)
    selected = rows[within : within + limit]
    consumed = offset + len(selected)
    return selected, {
        "total": total,
        "offset": offset,
        "limit": limit,
        "page": offset // ADVANCED_PAGE_SIZE + 1,
        "page_size": ADVANCED_PAGE_SIZE,
        "next_offset": consumed if selected and consumed < total else None,
    }


def search(query: str, args: argparse.Namespace, http: HTTP) -> dict[str, Any]:
    if not 1 <= args.limit <= 50:
        raise ValueError("limit must be 1..50")
    if args.offset < 0:
        raise ValueError("offset must be >= 0")
    if getattr(args, "mode", "local") == "advanced":
        if not query.strip() and not any(
            [
                getattr(args, "notion", []),
                getattr(args, "case", None),
                getattr(args, "filing", None),
                getattr(args, "tribunal", None),
                getattr(args, "date_from", None),
                getattr(args, "date_to", None),
            ]
        ):
            raise ValueError("Advanced mode needs a keyword or at least one facet")
        form, form_meta = http.soup(ADVANCED_URL, headers=_headers())
        params = _advanced_params(form, query, args, args.offset)
        result_soup, meta = http.soup(ADVANCED_URL, params, headers=_headers())
        rows, pagination = _parse_advanced_page(
            result_soup, meta, query, args.limit, args.offset
        )
        return {
            "status": "ok" if rows or pagination["total"] == 0 else "no-results-in-queried-index",
            "query": query,
            "mode": "advanced",
            "filters": {
                "notion": getattr(args, "notion", []),
                "case": getattr(args, "case", None),
                "filing": getattr(args, "filing", None),
                "tribunal": getattr(args, "tribunal", None),
                "date_from": getattr(args, "date_from", None),
                "date_to": getattr(args, "date_to", None),
            },
            "total": pagination["total"],
            "results": rows,
            "pagination": pagination,
            "scope": (
                "IRMCT CLD server-side advanced search over curated appellate extracts "
                "(full text, notions, case, filing, date and tribunal)"
            ),
            "evidence": http.evidence,
        }
    if not query.strip():
        raise ValueError("A non-empty query is required in local mode")
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
