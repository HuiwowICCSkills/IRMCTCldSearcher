"""Offline tests for IRMCTCldSearcher."""
from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import cld_adapter as adapter  # noqa: E402


class FakeHttp:
    def __init__(self, data):
        self.data = data
        self.evidence = []

    def json(self, url, params=None, headers=None):
        return self.data, {
            "source_url": url, "http_status": 200, "content_type": "application/json",
            "bytes": 100, "retrieved_at": "2026-11-09T00:00:00Z", "sha256": "0" * 64,
        }


def args(**kwargs):
    base = dict(limit=2, offset=0, no_extract=True, cache=".cache",
                offline=False, cache_ttl=0, timeout=30)
    base.update(kwargs)
    return argparse.Namespace(**base)


class CldTests(unittest.TestCase):
    def test_search_filters_and_maps_fields(self):
        payload = {"data": [
            [1, "Command responsibility | Mens rea", "POPOVIC", "Appeal Judgement", "2015-01-30", None, None, None, None, None, None, None, "assets/filings/a.pdf"],
            [2, "Genocide", "OTHER", "Trial Judgement", "2020-01-01", None, None, None, None, None, None, None, "assets/filings/b.pdf"],
        ]}
        out = adapter.search("command", args(), FakeHttp(payload))
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["total"], 1)
        self.assertIn("POPOVIC", out["results"][0]["title"])
        self.assertEqual(out["results"][0]["date"], "2015-01-30")


if __name__ == "__main__":
    unittest.main()
