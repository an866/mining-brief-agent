"""Pydantic models for price quotes and trends."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    commodity: str
    date: date
    price: float
    unit: str = Field(description="Price unit including currency, e.g. 'USD/t'.")


class PriceQuote(BaseModel):
    """Result of ``get_price``."""

    commodity: str
    label: str
    date: date
    price: float
    unit: str
    provider: str = Field(description="'live' (fetched now) or 'snapshot' (offline demo series).")
    notes: list[str] = Field(default_factory=list)
    fetched_at: datetime


class TrendSeries(BaseModel):
    """Result of ``get_trend``."""

    commodity: str
    label: str
    days: int
    unit: str
    points: list[PricePoint]
    latest: PricePoint
    change_abs: float
    change_pct: float
    direction: Literal["up", "down", "flat"]
    sparkline: str = Field(description="Unicode sparkline of the window for quick visual scanning.")
    provider: str
    notes: list[str] = Field(default_factory=list)
    fetched_at: datetime
