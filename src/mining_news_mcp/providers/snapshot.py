"""Offline news corpus bundled with the repository.

The corpus exists so the whole pipeline — MCP stdio, agent orchestration,
brief composition — runs deterministically without any network access. It is
**demo content**: item titles are synthetic and must not be attributed to any
real outlet (see ``docs/data-sources.md``).

Timestamps are stored as relative offsets (``published_days_ago``) and rebased
onto the current date at load time, so a "last 7 days" query keeps returning a
meaningful window no matter when the demo is run.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from mining_brief_core import paths
from mining_brief_core.errors import DataNotFoundError, ProviderError

from ..models import Article, ArticleDetail, utcnow
from .base import ProviderOutcome

_TOKEN_SPLIT = re.compile(r"[^\w一-鿿]+", re.UNICODE)


class SnapshotItem(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_days_ago: int
    summary: str = ""
    body: str | None = None


class SnapshotCorpus(BaseModel):
    schema_: str = Field(alias="schema")
    note: str = ""
    items: list[SnapshotItem]


def _tokenize(text: str) -> list[str]:
    tokens = [t for t in _TOKEN_SPLIT.split(text.lower()) if t]
    return [t for t in tokens if len(t) >= 2 or "一" <= t <= "鿿"]


class SnapshotProvider:
    """Search/fetch backed by ``data/snapshots/news.json``."""

    DEMO_URL_PREFIX = "https://demo.example/news/"

    def __init__(self, corpus_path: Path | None = None) -> None:
        self._path = corpus_path or (paths.snapshots_dir() / "news.json")
        self._corpus: SnapshotCorpus | None = None

    def _load(self) -> SnapshotCorpus:
        if self._corpus is None:
            if not self._path.is_file():
                raise ProviderError(f"news snapshot corpus not found at {self._path}")
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            self._corpus = SnapshotCorpus.model_validate(payload)
        return self._corpus

    def search(self, query: str, days: int, limit: int) -> tuple[list[Article], ProviderOutcome]:
        corpus = self._load()
        tokens = _tokenize(query)

        scored: list[tuple[int, SnapshotItem]] = []
        for item in corpus.items:
            if item.published_days_ago > days:
                continue
            haystack = f"{item.title} {item.summary}".lower()
            score = sum(1 for token in tokens if token in haystack)
            if not tokens or score > 0:
                scored.append((score, item))

        scored.sort(key=lambda pair: (-pair[0], pair[1].published_days_ago, pair[1].id))
        now = utcnow()
        articles = [
            Article(
                id=item.id,
                title=item.title,
                url=item.url,
                source=item.source,
                published_at=now - timedelta(days=item.published_days_ago),
                summary=item.summary,
            )
            for _, item in scored[: max(limit, 0)]
        ]
        note = f"offline demo corpus ({len(corpus.items)} items); synthetic titles, see docs/data-sources.md"
        return articles, ProviderOutcome(mode="snapshot", notes=[note])

    def fetch_article(self, url: str) -> tuple[ArticleDetail, ProviderOutcome]:
        corpus = self._load()
        now = utcnow()
        for item in corpus.items:
            if item.url != url:
                continue
            if not item.body:
                raise ProviderError(
                    f"offline snapshot has no full text for {url!r}; "
                    "run with MINING_NEWS_SOURCE=live to fetch it from the network"
                )
            article = Article(
                id=item.id,
                title=item.title,
                url=item.url,
                source=item.source,
                published_at=now - timedelta(days=item.published_days_ago),
                summary=item.summary,
            )
            return (
                ArticleDetail(
                    article=article,
                    text=item.body,
                    word_count=len(item.body.split()),
                    fetched_at=now,
                    via="snapshot",
                ),
                ProviderOutcome(mode="snapshot", notes=["full text served from offline snapshot"]),
            )
        raise DataNotFoundError(f"URL not present in the offline snapshot corpus: {url}")
