"""Unit tests for the offline snapshot news provider."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mining_brief_core import paths
from mining_brief_core.errors import DataNotFoundError, ProviderError
from mining_news_mcp.providers.snapshot import SnapshotProvider

FIXTURE_CORPUS = {
    "schema": "mining-brief-agent/news-snapshot@1",
    "note": "test fixture",
    "items": [
        {
            "id": "p1",
            "title": "Pilbara lithium concentrate shipments rise",
            "url": "https://demo.example/news/p1",
            "source": "demo-wire",
            "published_days_ago": 1,
            "summary": "Shipments rose month-on-month.",
            "body": "Full body text for the Pilbara article. " * 5,
        },
        {
            "id": "p2",
            "title": "Pilbara expansion study advances",
            "url": "https://demo.example/news/p2",
            "source": "demo-wire",
            "published_days_ago": 9,
            "summary": "Feasibility stage reached.",
        },
        {
            "id": "c1",
            "title": "Copper holds gains as smelter margins recover",
            "url": "https://demo.example/news/c1",
            "source": "demo-wire",
            "published_days_ago": 2,
            "summary": "Three-month copper held above support.",
        },
    ],
}


@pytest.fixture()
def provider(tmp_path: Path) -> SnapshotProvider:
    corpus_file = tmp_path / "news.json"
    corpus_file.write_text(json.dumps(FIXTURE_CORPUS), encoding="utf-8")
    return SnapshotProvider(corpus_path=corpus_file)


def test_search_filters_by_days_window(provider: SnapshotProvider) -> None:
    items, outcome = provider.search("pilbara", days=7, limit=10)
    assert [item.id for item in items] == ["p1"]  # p2 is 9 days old
    assert outcome.mode == "snapshot"
    assert outcome.notes


def test_search_window_widens(provider: SnapshotProvider) -> None:
    items, _ = provider.search("pilbara", days=30, limit=10)
    assert [item.id for item in items] == ["p1", "p2"]  # sorted by recency


def test_search_empty_query_returns_everything_in_window(provider: SnapshotProvider) -> None:
    items, _ = provider.search("", days=7, limit=10)
    assert {item.id for item in items} == {"p1", "c1"}


def test_search_respects_limit(provider: SnapshotProvider) -> None:
    items, _ = provider.search("", days=30, limit=2)
    assert len(items) == 2


def test_search_rebases_dates_onto_now(provider: SnapshotProvider) -> None:
    items, _ = provider.search("pilbara", days=7, limit=10)
    now = datetime.now(UTC)
    assert abs(now - items[0].published_at - timedelta(days=1)) < timedelta(minutes=5)


def test_fetch_article_returns_body_from_snapshot(provider: SnapshotProvider) -> None:
    detail, outcome = provider.fetch_article("https://demo.example/news/p1")
    assert detail.via == "snapshot"
    assert detail.word_count > 5
    assert "Full body text" in detail.text
    assert outcome.mode == "snapshot"


def test_fetch_article_without_body_raises(provider: SnapshotProvider) -> None:
    with pytest.raises(ProviderError, match="no full text"):
        provider.fetch_article("https://demo.example/news/c1")


def test_fetch_article_unknown_url_raises(provider: SnapshotProvider) -> None:
    with pytest.raises(DataNotFoundError):
        provider.fetch_article("https://demo.example/news/missing")


def test_bundled_corpus_matches_pilbara_query() -> None:
    """The repository corpus itself must serve the demo query 'Pilbara lithium'."""
    provider = SnapshotProvider(paths.snapshots_dir() / "news.json")
    items, _ = provider.search("Pilbara Pilgangoora lithium", days=7, limit=10)
    assert len(items) >= 3
    # days_ago == 7 items sit exactly on the window edge; allow a minute of
    # clock skew between the provider's "now" and the test's.
    cutoff = datetime.now(UTC) - timedelta(days=7, minutes=1)
    assert all(item.published_at >= cutoff for item in items)
