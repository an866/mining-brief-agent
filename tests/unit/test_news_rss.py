"""Unit tests for the pure RSS parsing half of the live news provider."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from mining_news_mcp.providers.live import parse_feed

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

FALLBACK_NOW = datetime(2025, 10, 3, 12, 0, tzinfo=timezone.utc)


def _articles():
    payload = (FIXTURES / "sample_feed.xml").read_bytes()
    return parse_feed(payload, now=FALLBACK_NOW)


def test_parses_all_entries() -> None:
    articles = _articles()
    assert len(articles) == 3
    assert [a.url for a in articles] == [
        "https://demo.example/news/a",
        "https://demo.example/news/b",
        "https://demo.example/news/c",
    ]


def test_parses_pub_date_as_utc() -> None:
    articles = _articles()
    assert articles[0].published_at == datetime(2025, 10, 1, 8, 30, tzinfo=timezone.utc)
    assert articles[2].published_at == datetime(2025, 10, 2, 14, 5, tzinfo=timezone.utc)


def test_missing_date_falls_back_to_reference_now() -> None:
    articles = _articles()
    assert articles[1].published_at == FALLBACK_NOW


def test_strips_html_from_summary() -> None:
    articles = _articles()
    assert "<p>" not in articles[0].summary
    assert "Shipments" in articles[0].summary
    assert "rose" in articles[0].summary


def test_entry_source_prefers_item_source_then_feed_title() -> None:
    articles = _articles()
    assert articles[2].source == "Demo Bureau"
    assert articles[0].source == "Demo Mining Wire"
