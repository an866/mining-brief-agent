"""Unit tests for the pure price-trend analytics."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from lme_price_mcp.analytics import FLAT_THRESHOLD_PCT, sparkline, summarize
from lme_price_mcp.models import PricePoint

_BLOCKS = "▁▂▃▄▅▆▇█"


def _points(prices: list[float]) -> list[PricePoint]:
    base = date(2025, 10, 1)
    return [
        PricePoint(commodity="copper", date=base + timedelta(days=i), price=p, unit="USD/t")
        for i, p in enumerate(prices)
    ]


class TestSparkline:
    def test_length_matches_input(self) -> None:
        assert len(sparkline([1.0, 2.0, 3.0])) == 3

    def test_only_block_characters(self) -> None:
        rendered = sparkline([1.0, 5.0, 2.0, 8.0])
        assert all(char in _BLOCKS for char in rendered)
        assert rendered[0] == _BLOCKS[0]  # minimum

    def test_constant_series_renders_mid_block(self) -> None:
        rendered = sparkline([7.0] * 5)
        assert rendered == _BLOCKS[len(_BLOCKS) // 2] * 5

    def test_downsampling_keeps_width(self) -> None:
        rendered = sparkline(list(range(100)), width=20)
        assert len(rendered) == 20

    def test_empty_series(self) -> None:
        assert sparkline([]) == ""


class TestSummarize:
    def test_detects_uptrend(self) -> None:
        summary = summarize(_points([100.0, 102.0, 105.0, 110.0]))
        assert summary.direction == "up"
        assert summary.change_abs == pytest.approx(10.0)
        assert summary.change_pct == pytest.approx(10.0)
        assert summary.latest.price == pytest.approx(110.0)

    def test_detects_downtrend(self) -> None:
        summary = summarize(_points([100.0, 95.0, 90.0]))
        assert summary.direction == "down"
        assert summary.change_pct == pytest.approx(-10.0)

    def test_small_move_is_flat(self) -> None:
        moved = 100.0 * (1.0 + FLAT_THRESHOLD_PCT / 100.0 / 2)
        summary = summarize(_points([100.0, moved]))
        assert summary.direction == "flat"

    def test_requires_points(self) -> None:
        with pytest.raises(ValueError):
            summarize([])
