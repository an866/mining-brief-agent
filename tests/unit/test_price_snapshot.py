"""Unit tests for the offline snapshot price provider."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from lme_price_mcp.commodities import COMMODITIES
from lme_price_mcp.providers.snapshot import SnapshotPriceProvider
from mining_brief_core.errors import DataNotFoundError, ProviderError

SNAPSHOT = {
    "schema": "mining-brief-agent/price-snapshot@1",
    "commodity": "copper",
    "unit": "USD/t",
    "synthetic": True,
    "note": "test fixture",
    "points": [
        {"days_ago": 2, "price": 100.0},
        {"days_ago": 1, "price": 101.0},
        {"days_ago": 0, "price": 102.0},
    ],
}


@pytest.fixture()
def provider(tmp_path: Path) -> SnapshotPriceProvider:
    (tmp_path / "copper.json").write_text(json.dumps(SNAPSHOT), encoding="utf-8")
    return SnapshotPriceProvider(snapshot_dir=tmp_path)


def test_latest_quote(provider: SnapshotPriceProvider) -> None:
    point, outcome = provider.get_quote(COMMODITIES["copper"], None)
    assert point.price == 102.0
    assert point.date == date.today()
    assert point.unit == "USD/t"
    assert outcome.mode == "snapshot"
    assert outcome.notes


def test_quote_by_date(provider: SnapshotPriceProvider) -> None:
    target = date.today() - timedelta(days=1)
    point, _ = provider.get_quote(COMMODITIES["copper"], target)
    assert point.price == 101.0
    assert point.date == target


def test_quote_outside_window_raises(provider: SnapshotPriceProvider) -> None:
    with pytest.raises(DataNotFoundError, match="available"):
        provider.get_quote(COMMODITIES["copper"], date.today() - timedelta(days=30))


def test_series_window(provider: SnapshotPriceProvider) -> None:
    points, _ = provider.get_series(COMMODITIES["copper"], days=2)
    assert [p.price for p in points] == [100.0, 101.0, 102.0]
    assert [p.date for p in points] == sorted(p.date for p in points)


def test_series_narrow_window(provider: SnapshotPriceProvider) -> None:
    points, _ = provider.get_series(COMMODITIES["copper"], days=1)
    assert [p.price for p in points] == [101.0, 102.0]


def test_missing_snapshot_file_raises(tmp_path: Path) -> None:
    provider = SnapshotPriceProvider(snapshot_dir=tmp_path)
    with pytest.raises(ProviderError, match="snapshot not found"):
        provider.get_quote(COMMODITIES["zinc"], None)
