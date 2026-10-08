"""The provider interface and its outcome metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from ..commodities import CommoditySpec
from ..models import PricePoint


@dataclass
class ProviderOutcome:
    mode: str
    notes: list[str] = field(default_factory=list)


class PriceProvider(Protocol):
    """Interface implemented by the live and snapshot backends."""

    def get_quote(self, spec: CommoditySpec, on: date | None) -> tuple[PricePoint, ProviderOutcome]:
        """Return the price for ``on`` (a date) or the latest available."""
        ...

    def get_series(self, spec: CommoditySpec, days: int) -> tuple[list[PricePoint], ProviderOutcome]:
        """Return a daily series covering the last ``days`` days."""
        ...
