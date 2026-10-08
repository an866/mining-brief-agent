"""Best-effort live price backend: Sina finance realtime quotes.

``hq.sinajs.cn`` serves realtime quotes for LME 3-month contracts (``hf_``
symbols) and Chinese futures main contracts (``nf_`` symbols) as GBK-encoded
JavaScript. It requires a finance.sina.com.cn ``Referer`` header and it only
answers *latest* quotes — history comes from the snapshot channel, which is
why :meth:`LivePriceProvider.get_series` raises.

The wire format differs between the two symbol families and is not formally
documented by Sina; the parsers below are unit-tested against recorded sample
payloads and any format drift degrades gracefully to the snapshot channel.
"""

from __future__ import annotations

from datetime import date

from mining_brief_core.errors import FetchError, ProviderError
from mining_brief_core.http import fetch_text

from ..commodities import CommoditySpec
from ..models import PricePoint
from .base import ProviderOutcome

QUOTE_URL_TEMPLATE = "https://hq.sinajs.cn/list={symbols}"
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn"}


def parse_hq_response(payload: str, symbol: str) -> float:
    """Parse one ``hq_str_<symbol>="..."`` assignment into a price.

    ``hf_`` (LME) payloads carry the latest price in field 0; ``nf_``
    (domestic futures) payloads carry it in field 8. An empty assignment
    (``hq_str_...="";``) means Sina has no data for the symbol.
    """
    marker = f'hq_str_{symbol}="'
    start = payload.find(marker)
    if start == -1:
        raise ProviderError(f"symbol {symbol!r} not present in quote response")
    start += len(marker)
    end = payload.find('"', start)
    if end == -1:
        raise ProviderError(f"malformed quote response for {symbol!r}: unterminated string")
    fields = payload[start:end].split(",")
    if not fields or not fields[0]:
        raise ProviderError(f"empty quote for {symbol!r} (market closed or symbol changed)")

    index = 0 if symbol.startswith("hf_") else 8
    if index >= len(fields):
        raise ProviderError(f"quote for {symbol!r} has fewer than {index + 1} fields")
    try:
        return float(fields[index])
    except ValueError as exc:
        raise ProviderError(
            f"quote for {symbol!r} field {index} is not numeric: {fields[index]!r}"
        ) from exc


class LivePriceProvider:
    """Realtime quotes via Sina finance; latest value only."""

    def get_quote(self, spec: CommoditySpec, on: date | None) -> tuple[PricePoint, ProviderOutcome]:
        if spec.live_symbol is None:
            raise ProviderError(f"{spec.key} has no live symbol configured")
        if on is not None and on != date.today():
            raise ProviderError(
                "live quotes only serve the current price; pass no date, or rely on the "
                "snapshot channel for historical dates"
            )
        try:
            payload = fetch_text(
                QUOTE_URL_TEMPLATE.format(symbols=spec.live_symbol),
                timeout=8.0,
                headers=SINA_HEADERS,
            )
        except FetchError as exc:
            raise ProviderError(f"live quote fetch failed: {exc}") from exc
        price = parse_hq_response(payload, spec.live_symbol)
        point = PricePoint(commodity=spec.key, date=date.today(), price=price, unit=spec.unit)
        return point, ProviderOutcome(mode="live", notes=[f"sina symbol {spec.live_symbol}"])

    def get_series(
        self, spec: CommoditySpec, days: int
    ) -> tuple[list[PricePoint], ProviderOutcome]:
        raise ProviderError(
            "the live quote endpoint provides no history; trend comes from the snapshot channel"
        )
