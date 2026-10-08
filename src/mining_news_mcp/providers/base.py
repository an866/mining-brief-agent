"""The provider interface and its outcome metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..models import Article, ArticleDetail


@dataclass
class ProviderOutcome:
    """Metadata about how a provider produced its data."""

    mode: str
    notes: list[str] = field(default_factory=list)


class NewsProvider(Protocol):
    """Interface implemented by the live and snapshot backends."""

    def search(self, query: str, days: int, limit: int) -> tuple[list[Article], ProviderOutcome]:
        """Return articles matching ``query`` published within the last ``days`` days."""
        ...

    def fetch_article(self, url: str) -> tuple[ArticleDetail, ProviderOutcome]:
        """Return the full text of the article at ``url``."""
        ...
