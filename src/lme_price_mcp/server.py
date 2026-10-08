"""lme-price-mcp — exposes ``get_price`` and ``get_trend`` over MCP."""

from __future__ import annotations

from datetime import date as date_type

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mining_brief_core.errors import DataNotFoundError, MiningBriefError
from mining_brief_core.logging_setup import configure_logging

from . import __version__
from .commodities import resolve_commodity
from .models import PriceQuote, TrendSeries
from .providers import get_price_service

SERVER_NAME = "lme-price-mcp"

_MIN_DAYS = 2
_MAX_DAYS = 180


def build_server() -> MCPServer:
    """Build the ``lme-price-mcp`` server."""
    server = MCPServer(
        name=SERVER_NAME,
        title="LME & SHFE Prices",
        description=(
            "Commodity price quotes and trends for LME copper/zinc/nickel (USD/t), "
            "lithium carbonate (CNY/t) and iron ore (CNY/t). Live quotes where "
            "reachable; historical series from a bundled offline snapshot."
        ),
        version=__version__,
    )

    @server.tool(
        name="get_price",
        description=(
            "Get the price of one commodity (copper/铜, zinc/锌, nickel/镍, "
            "lithium_carbonate/碳酸锂, iron_ore/铁矿石) for a given ISO date "
            "(YYYY-MM-DD), or the latest available price when date is omitted."
        ),
    )
    def get_price(commodity: str, date: str | None = None) -> PriceQuote:
        try:
            spec = resolve_commodity(commodity)
        except DataNotFoundError as exc:
            raise ToolError(str(exc)) from exc

        parsed: date_type | None = None
        if date is not None and str(date).strip():
            try:
                parsed = date_type.fromisoformat(str(date).strip())
            except ValueError as exc:
                raise ToolError(f"invalid date {date!r}: expected ISO format YYYY-MM-DD") from exc

        try:
            return get_price_service().quote(spec, parsed)
        except MiningBriefError as exc:
            raise ToolError(f"get_price failed for {commodity!r}: {exc}") from exc

    @server.tool(
        name="get_trend",
        description=(
            "Get the price trend of one commodity over the last `days` days "
            f"({_MIN_DAYS}-{_MAX_DAYS}, default 30): daily points, absolute and "
            "percent change, direction (up/down/flat), and a unicode sparkline."
        ),
    )
    def get_trend(commodity: str, days: int = 30) -> TrendSeries:
        try:
            spec = resolve_commodity(commodity)
        except DataNotFoundError as exc:
            raise ToolError(str(exc)) from exc

        clamped_days = max(_MIN_DAYS, min(int(days), _MAX_DAYS))
        try:
            return get_price_service().trend(spec, clamped_days)
        except MiningBriefError as exc:
            raise ToolError(f"get_trend failed for {commodity!r}: {exc}") from exc

    return server


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    configure_logging(SERVER_NAME)
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
