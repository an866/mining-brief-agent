"""mining-news-mcp — FastMCP-style server exposing ``search`` and ``fetch_article``.

Tool bodies are sync functions: the SDK runs them on a worker thread, so the
stdio event loop stays responsive (the agent calls tools in parallel). Domain
errors are translated to ``ToolError`` so the client sees the real message
instead of a sanitized crash.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mining_brief_core.errors import MiningBriefError
from mining_brief_core.logging_setup import configure_logging

from . import __version__
from .models import ArticleDetail, SearchResult, utcnow
from .providers import get_news_provider

SERVER_NAME = "mining-news-mcp"

_MAX_SEARCH_DAYS = 90
_MAX_SEARCH_LIMIT = 50


def build_server() -> MCPServer:
    """Build the ``mining-news-mcp`` server with its tools registered."""
    server = MCPServer(
        name=SERVER_NAME,
        title="Mining News",
        description=(
            "Search mining-industry news (mining.com / Google News RSS) and fetch "
            "article full text. Falls back to a bundled offline snapshot corpus when "
            "the live web is unreachable."
        ),
        version=__version__,
    )

    @server.tool(
        name="search",
        description=(
            "Search mining news published within the last `days` days (default 7). "
            "Returns title/source/date/summary/url for each result, plus which backend "
            "served it ('live' or 'snapshot'). Query is matched against title+summary; "
            "use 2-4 keywords, e.g. 'Pilbara lithium'."
        ),
    )
    def search(query: str, days: int = 7, limit: int = 10) -> SearchResult:
        clamped_days = max(1, min(int(days), _MAX_SEARCH_DAYS))
        clamped_limit = max(1, min(int(limit), _MAX_SEARCH_LIMIT))
        try:
            items, outcome = get_news_provider().search(query, clamped_days, clamped_limit)
        except MiningBriefError as exc:
            raise ToolError(f"news search failed: {exc}") from exc
        return SearchResult(
            query=query,
            days=clamped_days,
            items=items,
            provider=outcome.mode,
            notes=outcome.notes,
            fetched_at=utcnow(),
        )

    @server.tool(
        name="fetch_article",
        description=(
            "Fetch one news article by its URL and return the extracted full text "
            "(title, body, word count). Use after `search` to read promising items in "
            "detail. Works for any http(s) article URL."
        ),
    )
    def fetch_article(url: str) -> ArticleDetail:
        try:
            detail, _outcome = get_news_provider().fetch_article(url)
        except MiningBriefError as exc:
            raise ToolError(f"fetch_article failed for {url}: {exc}") from exc
        return detail

    return server


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    configure_logging(SERVER_NAME)
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
