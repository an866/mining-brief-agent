"""Readability-lite HTML article extraction.

Given a news page, return its title, main body text, and — when the page
exposes it — the publication time. Deliberately dependency-light: BeautifulSoup
with the stdlib ``html.parser`` only, no lxml/readability C extensions, so the
same code runs identically in CI, locally, and in the slim Docker image.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import BaseModel

_STRIP_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "iframe",
    "svg",
    "button",
)

# Class/id fragments that mark boilerplate rather than article content.
_JUNK_PATTERN = re.compile(
    r"advert|sponsor|share|social|comment|related|newsletter|subscribe|promo|"
    r"banner|cookie|popup|paywall|breadcrumb|menu|sidebar",
    re.IGNORECASE,
)

# Paragraphs shorter than this are usually captions or UI labels.
_MIN_PARAGRAPH_CHARS = 30
_MAX_TEXT_CHARS = 20_000

_META_DATE_PROPERTIES = ("article:published_time", "og:published_time", "datePublished")
_DATE_TEXT_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?"
)


class ExtractedArticle(BaseModel):
    title: str
    text: str
    published_at: datetime | None = None


def _parse_datetime(raw: str) -> datetime | None:
    match = _DATE_TEXT_PATTERN.search(raw or "")
    if not match:
        return None
    value = match.group(0).replace(" ", "T").replace("Z", "+00:00")
    # Normalize "+0800" (no colon) which fromisoformat rejects before 3.11 semantics.
    if re.search(r"[+-]\d{4}$", value):
        value = value[:-5] + value[-5:-2] + ":" + value[-2:]
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _meta_content(
    soup: BeautifulSoup, *, prop: str | None = None, name: str | None = None
) -> str | None:
    attrs: dict[str, str] = {}
    if prop:
        attrs["property"] = prop
    if name:
        attrs["name"] = name
    tag = soup.find("meta", attrs=attrs)
    if isinstance(tag, Tag):
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _extract_published(soup: BeautifulSoup) -> datetime | None:
    for prop in _META_DATE_PROPERTIES:
        parsed = _parse_datetime(_meta_content(soup, prop=prop) or "")
        if parsed:
            return parsed

    time_tag = soup.find("time")
    if isinstance(time_tag, Tag):
        parsed = _parse_datetime(
            str(time_tag.get("datetime") or time_tag.get_text(" ", strip=True))
        )
        if parsed:
            return parsed

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "{}")
        except (ValueError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if isinstance(candidate, dict):
                parsed = _parse_datetime(str(candidate.get("datePublished", "")))
                if parsed:
                    return parsed
    return None


def _strip_boilerplate(soup: BeautifulSoup) -> None:
    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    for tag in soup.find_all(attrs={"class": _JUNK_PATTERN}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": _JUNK_PATTERN}):
        tag.decompose()


def _container_score(container: Tag) -> int:
    return sum(len(p.get_text(" ", strip=True)) for p in container.find_all("p"))


def _paragraph_text(container: Tag) -> str:
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in container.find_all("p")
        if len(p.get_text(" ", strip=True)) >= _MIN_PARAGRAPH_CHARS
    ]
    text = "\n\n".join(paragraphs)
    if len(text) < 200:
        # Fallback for pages that don't mark up paragraphs well.
        text = container.get_text("\n", strip=True)
    return text[:_MAX_TEXT_CHARS]


def extract_article(html: str, url: str) -> ExtractedArticle:
    """Extract (title, main text, published time) from an article page."""
    soup = BeautifulSoup(html, "html.parser")

    title = (
        _meta_content(soup, prop="og:title")
        or (soup.title.get_text(strip=True) if soup.title else None)
        or (soup.h1.get_text(" ", strip=True) if soup.h1 else None)
        or url
    )

    published = _extract_published(soup)
    _strip_boilerplate(soup)

    candidates: list[Tag] = list(soup.find_all("article"))
    main = soup.find("main")
    if isinstance(main, Tag):
        candidates.append(main)
    if not candidates:
        candidates = [c for c in soup.find_all("div") if c.find("p")]

    if not candidates:
        body = soup.body
        text = body.get_text("\n", strip=True)[:_MAX_TEXT_CHARS] if isinstance(body, Tag) else ""
        return ExtractedArticle(title=title, text=text, published_at=published)

    best = max(candidates, key=_container_score)
    return ExtractedArticle(title=title, text=_paragraph_text(best), published_at=published)
