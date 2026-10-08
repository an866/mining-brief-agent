"""Price service: provider selection, mode handling and graceful degradation.

``MINING_PRICE_SOURCE`` selects the channel: ``auto`` (default) | ``live`` |
``snapshot``.

* Quotes: in ``auto`` the live endpoint is tried first (latest price only);
  any failure falls back to the snapshot channel with a note.
* Trends: history lives in the snapshot channel; in ``auto`` the *latest*
  live point is merged onto the snapshot series when reachable, so the demo
  still shows a fresh last tick when the network cooperates — and degrades to
  pure snapshot when it doesn't.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

from mining_brief_core.errors import ProviderError

from ..analytics import sparkline, summarize
from ..commodities import CommoditySpec
from ..models import PricePoint, PriceQuote, TrendSeries
from .base import ProviderOutcome
from .live import LivePriceProvider
from .snapshot import SnapshotPriceProvider

MODE_ENV_VAR = "MINING_PRICE_SOURCE"
VALID_MODES = ("auto", "live", "snapshot")

__all__ = [
    "MODE_ENV_VAR",
    "VALID_MODES",
    "PriceService",
    "ProviderOutcome",
    "get_mode",
    "get_price_service",
]


def get_mode() -> str:
    raw = os.environ.get(MODE_ENV_VAR, "auto").strip().lower()
    return raw if raw in VALID_MODES else "auto"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PriceService:
    """The composition layer the MCP tools call into."""

    def __init__(self) -> None:
        self._live = LivePriceProvider()
        self._snapshot = SnapshotPriceProvider()

    def quote(self, spec: CommoditySpec, on: date | None) -> PriceQuote:
        mode = get_mode()
        if mode == "snapshot":
            point, outcome = self._snapshot.get_quote(spec, on)
        elif mode == "live":
            point, outcome = self._live.get_quote(spec, on)
        elif on is not None:
            # Historical date: only the snapshot channel can serve it.
            point, outcome = self._snapshot.get_quote(spec, on)
            outcome.notes.append("historical dates are served from the snapshot channel")
        else:
            try:
                point, outcome = self._live.get_quote(spec, None)
            except ProviderError as exc:
                point, outcome = self._snapshot.get_quote(spec, None)
                outcome.notes.insert(0, f"live quote unavailable ({exc}); served from snapshot")

        return PriceQuote(
            commodity=spec.key,
            label=spec.label_en,
            date=point.date,
            price=point.price,
            unit=point.unit,
            provider=outcome.mode,
            notes=outcome.notes,
            fetched_at=_utcnow(),
        )

    def trend(self, spec: CommoditySpec, days: int) -> TrendSeries:
        mode = get_mode()
        if mode == "live":
            points, outcome = self._live.get_series(spec, days)  # raises: no history live
        else:
            points, outcome = self._snapshot.get_series(spec, days)
            if mode == "auto":
                points, outcome = self._merge_live_latest(spec, points, outcome)

        summary = summarize(points)
        return TrendSeries(
            commodity=spec.key,
            label=spec.label_en,
            days=days,
            unit=points[0].unit,
            points=points,
            latest=summary.latest,
            change_abs=summary.change_abs,
            change_pct=summary.change_pct,
            direction=summary.direction,
            sparkline=sparkline([p.price for p in points]),
            provider=outcome.mode,
            notes=outcome.notes,
            fetched_at=_utcnow(),
        )

    def _merge_live_latest(
        self,
        spec: CommoditySpec,
        points: list[PricePoint],
        outcome: ProviderOutcome,
    ) -> tuple[list[PricePoint], ProviderOutcome]:
        try:
            live_point, _ = self._live.get_quote(spec, None)
        except ProviderError:
            return points, outcome
        if not points or live_point.date >= points[-1].date:
            merged = [p for p in points if p.date != live_point.date] + [live_point]
            merged.sort(key=lambda p: p.date)
            notes = list(outcome.notes)
            notes.append("latest tick merged from the live quote channel")
            return merged, ProviderOutcome(mode="snapshot+live", notes=notes)
        return points, outcome


def get_price_service() -> PriceService:
    return PriceService()
