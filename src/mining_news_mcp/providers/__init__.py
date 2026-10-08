"""Provider selection for the news server.

Two interchangeable backends implement the same tiny interface:

* ``live``     – fetch mining.com / Google News RSS right now.
* ``snapshot`` – read the offline demo corpus bundled in ``data/snapshots``.

The mode is chosen with ``MINING_NEWS_SOURCE`` = ``auto`` (default) | ``live``
| ``snapshot``. In ``auto`` mode the live backend is tried first and the
snapshot is used as a graceful fallback — every fallback is recorded in the
result's ``notes`` so the brief can state which channel it used.
"""

from __future__ import annotations

import os

from ..models import Article, ArticleDetail
from .base import NewsProvider, ProviderOutcome
from .live import LiveNewsProvider
from .snapshot import SnapshotProvider

MODE_ENV_VAR = "MINING_NEWS_SOURCE"
VALID_MODES = ("auto", "live", "snapshot")

__all__ = [
    "MODE_ENV_VAR",
    "VALID_MODES",
    "AutoNewsProvider",
    "NewsProvider",
    "ProviderOutcome",
    "get_news_provider",
    "get_source_mode",
]


def get_source_mode() -> str:
    raw = os.environ.get(MODE_ENV_VAR, "auto").strip().lower()
    return raw if raw in VALID_MODES else "auto"


class AutoNewsProvider:
    """Compose the live and snapshot providers with graceful degradation."""

    def __init__(self) -> None:
        self._live = LiveNewsProvider()
        self._snapshot = SnapshotProvider()

    def search(self, query: str, days: int, limit: int) -> tuple[list[Article], ProviderOutcome]:
        mode = get_source_mode()
        if mode == "live":
            return self._live.search(query, days, limit)
        if mode == "snapshot":
            return self._snapshot.search(query, days, limit)

        try:
            return self._live.search(query, days, limit)
        except Exception as exc:
            items, outcome = self._snapshot.search(query, days, limit)
            outcome.notes.insert(
                0,
                f"live news unavailable ({type(exc).__name__}: {exc}); served from offline snapshot",
            )
            return items, outcome

    def fetch_article(self, url: str) -> tuple[ArticleDetail, ProviderOutcome]:
        mode = get_source_mode()
        if mode == "snapshot" or url.startswith(SnapshotProvider.DEMO_URL_PREFIX):
            return self._snapshot.fetch_article(url)
        if mode == "live":
            return self._live.fetch_article(url)

        try:
            return self._live.fetch_article(url)
        except Exception as exc:
            detail, outcome = self._snapshot.fetch_article(url)
            outcome.notes.insert(
                0,
                f"live fetch failed ({type(exc).__name__}: {exc}); served from offline snapshot",
            )
            return detail, outcome


def get_news_provider() -> NewsProvider:
    """Build the provider for the current mode. Constructed per call; cheap."""
    return AutoNewsProvider()
