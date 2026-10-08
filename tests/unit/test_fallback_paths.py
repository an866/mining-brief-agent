"""Tests for the graceful-degradation paths — the project's honesty contract.

Every fallback must (a) still return usable data and (b) be recorded in the
outcome notes so the report can disclose the channel it actually used. These
tests fake the live backends; the snapshot side uses the bundled demo data.
"""

from __future__ import annotations

from datetime import date

import pytest

from lme_price_mcp.commodities import COMMODITIES
from lme_price_mcp.models import PricePoint
from lme_price_mcp.providers import PriceService
from lme_price_mcp.providers.base import ProviderOutcome
from mining_brief_core.errors import ProviderError
from mining_news_mcp.providers import AutoNewsProvider


class _FailingNews:
    def search(self, query: str, days: int, limit: int):
        raise ProviderError("simulated network down")

    def fetch_article(self, url: str):
        raise ProviderError("simulated network down")


class _FailingPrices:
    def get_quote(self, spec, on):
        raise ProviderError("simulated network down")

    def get_series(self, spec, days):
        raise ProviderError("simulated network down")


class _LiveOnlyPrices:
    """A live backend that can serve the latest quote but has no history."""

    def get_quote(self, spec, on):
        point = PricePoint(commodity=spec.key, date=date.today(), price=99999.0, unit=spec.unit)
        return point, ProviderOutcome(mode="live")

    def get_series(self, spec, days):
        raise ProviderError("no history live")


def test_news_search_falls_back_to_snapshot_with_note(monkeypatch) -> None:
    provider = AutoNewsProvider()
    monkeypatch.setattr(provider, "_live", _FailingNews())
    items, outcome = provider.search("Pilbara lithium", days=7, limit=5)
    assert items
    assert outcome.mode == "snapshot"
    assert "live news unavailable" in outcome.notes[0]


def test_news_fetch_reports_both_failures(monkeypatch) -> None:
    provider = AutoNewsProvider()
    monkeypatch.setattr(provider, "_live", _FailingNews())
    with pytest.raises(ProviderError) as excinfo:
        provider.fetch_article("https://real-news.example/article/1")
    message = str(excinfo.value)
    assert "live" in message
    assert "snapshot" in message


def test_price_quote_falls_back_to_snapshot_with_note(monkeypatch) -> None:
    service = PriceService()
    monkeypatch.setattr(service, "_live", _FailingPrices())
    quote = service.quote(COMMODITIES["copper"], None)
    assert quote.provider == "snapshot"
    assert "live quote unavailable" in quote.notes[0]


def test_price_trend_merges_live_latest_with_note(monkeypatch) -> None:
    service = PriceService()
    monkeypatch.setattr(service, "_live", _LiveOnlyPrices())
    trend = service.trend(COMMODITIES["copper"], days=30)
    assert trend.provider == "snapshot+live"
    assert any("merged from the live" in note for note in trend.notes)
    assert trend.latest.price == 99999.0


def test_price_trend_pure_snapshot_when_live_down(monkeypatch) -> None:
    service = PriceService()
    monkeypatch.setattr(service, "_live", _FailingPrices())
    trend = service.trend(COMMODITIES["copper"], days=30)
    assert trend.provider == "snapshot"
    assert trend.latest.price != 99999.0


def test_decode_text_handles_utf8_and_gb18030() -> None:
    from mining_brief_core.http import decode_text

    original = "碳酸锂价格企稳，澳矿发运回升"
    assert decode_text(original.encode("utf-8")) == original
    assert decode_text(original.encode("gb18030")) == original
