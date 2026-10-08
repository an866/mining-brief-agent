"""Live news backend: mining.com and Google News RSS.

The parsing half of this module (:func:`parse_feed`) is a pure function over
feed bytes so it can be unit-tested against recorded fixtures; the network
half is thin on purpose. Individual feeds may fail (Cloudflare, regional
blocks) without sinking the whole search — failures are collected as notes.
"""

from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

import feedparser

from mining_brief_core.errors import FetchError, ProviderError
from mining_brief_core.http import fetch_text

from ..extract import extract_article
from ..models import Article, ArticleDetail, utcnow
from .base import ProviderOutcome

GOOGLE_NEWS_RSS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
MINING_COM_FEED = "https://www.mining.com/feed/"

_TAG_RE = re.compile(r"<[^>]+>")
_MAX_ARTICLE_CHARS = 20_000


def _strip_html(raw: str) -> str:
    if "<" not in raw:
        return raw.strip()
    return _TAG_RE.sub(" ", raw).strip()


def _struct_time_to_utc(value: object) -> datetime | None:
    if not isinstance(value, tuple) or len(value) < 6:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)
    except (OverflowError, OSError, TypeError, ValueError):
        return None


def _entry_published(entry: feedparser.FeedParserDict, fallback: datetime) -> datetime:
    return (
        _struct_time_to_utc(entry.get("published_parsed"))
        or _struct_time_to_utc(entry.get("updated_parsed"))
        or fallback
    )


def _entry_source(entry: feedparser.FeedParserDict, feed_title: str) -> str:
    source = entry.get("source")
    if isinstance(source, dict):
        title = source.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    if feed_title.strip():
        return feed_title.strip()
    return "unknown"


def parse_feed(feed_bytes: bytes, *, now: datetime | None = None) -> list[Article]:
    """Parse an RSS/Atom feed payload into articles (pure function)."""
    reference_now = now or utcnow()
    parsed = feedparser.parse(feed_bytes)
    feed_title_raw = parsed.feed.get("title", "") if parsed.feed else ""
    feed_title = str(feed_title_raw)

    articles: list[Article] = []
    for entry in parsed.entries:
        link = str(entry.get("link") or "").strip()
        title = str(entry.get("title") or "").strip()
        if not link or not title:
            continue
        summary_raw = str(entry.get("summary") or entry.get("description") or "")
        articles.append(
            Article(
                id=str(entry.get("id") or link),
                title=title,
                url=link,
                source=_entry_source(entry, feed_title),
                published_at=_entry_published(entry, reference_now),
                summary=_strip_html(summary_raw)[:600],
            )
        )
    return articles


def _dedupe(articles: list[Article]) -> list[Article]:
    seen: set[tuple[str, str]] = set()
    unique: list[Article] = []
    for article in articles:
        key = (article.title.lower(), article.url.split("?")[0])
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


class LiveNewsProvider:
    """Fetch real news feeds over the network."""

    def search(self, query: str, days: int, limit: int) -> tuple[list[Article], ProviderOutcome]:
        now = utcnow()
        cutoff = now - timedelta(days=days)

        feed_urls: list[str] = []
        if query.strip():
            feed_urls.append(GOOGLE_NEWS_RSS_TEMPLATE.format(query=quote_plus(query.strip())))
        feed_urls.append(MINING_COM_FEED)

        collected: list[Article] = []
        notes: list[str] = []
        for feed_url in feed_urls:
            try:
                payload = fetch_text(feed_url, timeout=12.0).encode("utf-8", errors="replace")
                collected.extend(parse_feed(payload, now=now))
            except FetchError as exc:
                notes.append(f"feed unavailable: {exc}")

        fresh = [a for a in collected if a.published_at >= cutoff]
        fresh = _dedupe(fresh)
        fresh.sort(key=lambda a: a.published_at, reverse=True)
        fresh = fresh[: max(limit, 0)]

        if not fresh:
            detail = "; ".join(notes) if notes else "feeds returned no items in window"
            raise ProviderError(f"no live news results for {query!r} within {days} days ({detail})")

        return fresh, ProviderOutcome(mode="live", notes=notes)

    def fetch_article(self, url: str) -> tuple[ArticleDetail, ProviderOutcome]:
        html = fetch_text(url, timeout=15.0)
        extracted = extract_article(html, url)
        if len(extracted.text) < 100:
            raise FetchError(f"could not extract a usable article body from {url}")
        now = utcnow()
        article = Article(
            id=url,
            title=extracted.title,
            url=url,
            source=_hostname(url),
            published_at=extracted.published_at or now,
            summary=extracted.text[:280],
        )
        text = extracted.text[:_MAX_ARTICLE_CHARS]
        return (
            ArticleDetail(
                article=article,
                text=text,
                word_count=len(text.split()),
                fetched_at=now,
                via="live",
            ),
            ProviderOutcome(mode="live"),
        )


def _hostname(url: str) -> str:
    match = re.match(r"https?://([^/]+)", url)
    return match.group(1) if match else "unknown"
