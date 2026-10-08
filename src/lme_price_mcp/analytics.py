"""Pure trend analytics: sparklines and windowed change summaries.

No I/O and no dependency on the provider layer — trivially unit-testable and
reusable by the agent's composer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .models import PricePoint

_BLOCKS = "▁▂▃▄▅▆▇█"

# |change| below this percentage is reported as "flat", so noise does not get
# dressed up as a trend in the brief's risk section.
FLAT_THRESHOLD_PCT = 0.5

Direction = Literal["up", "down", "flat"]


@dataclass(frozen=True)
class TrendSummary:
    latest: PricePoint
    change_abs: float
    change_pct: float
    direction: Direction


def sparkline(prices: Sequence[float], width: int = 32) -> str:
    """Render the (last ``width`` of the) series as unicode block characters."""
    values = list(prices)
    if not values:
        return ""
    if len(values) > width:
        values = values[-width:]
    low, high = min(values), max(values)
    if high == low:
        return _BLOCKS[len(_BLOCKS) // 2] * len(values)
    span = high - low
    return "".join(_BLOCKS[int((value - low) / span * (len(_BLOCKS) - 1))] for value in values)


def summarize(points: Sequence[PricePoint]) -> TrendSummary:
    """Change over the window: last vs first, in absolute and percent terms."""
    ordered = sorted(points, key=lambda p: p.date)
    if not ordered:
        raise ValueError("summarize() needs at least one point")
    first, last = ordered[0], ordered[-1]
    change_abs = last.price - first.price
    if first.price == 0:
        change_pct = 0.0
    else:
        change_pct = change_abs / first.price * 100.0
    if change_pct > FLAT_THRESHOLD_PCT:
        direction: Direction = "up"
    elif change_pct < -FLAT_THRESHOLD_PCT:
        direction = "down"
    else:
        direction = "flat"
    return TrendSummary(
        latest=last,
        change_abs=round(change_abs, 2),
        change_pct=round(change_pct, 2),
        direction=direction,
    )
