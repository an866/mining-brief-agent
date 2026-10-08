"""Pydantic models shared by the news server and its providers.

All timestamps are timezone-aware UTC; the JSON wire form is ISO 8601.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class Article(BaseModel):
    """One news item as returned by ``search``."""

    id: str = Field(description="Stable identifier (feed entry id or URL).")
    title: str
    url: str
    source: str = Field(description="Publisher name, e.g. 'mining.com'.")
    published_at: datetime
    summary: str = ""


class ArticleDetail(BaseModel):
    """Full-text result of ``fetch_article``."""

    article: Article
    text: str
    word_count: int
    fetched_at: datetime
    via: str = Field(description="Which backend produced this: 'live' or 'snapshot'.")


class SearchResult(BaseModel):
    """Envelope returned by the ``search`` tool."""

    query: str
    days: int
    items: list[Article]
    provider: str = Field(description="Backend that produced the results: 'live' or 'snapshot'.")
    notes: list[str] = Field(
        default_factory=list,
        description="Non-fatal notices, e.g. a live feed failing and the snapshot fallback kicking in.",
    )
    fetched_at: datetime
