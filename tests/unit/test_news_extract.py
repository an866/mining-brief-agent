"""Unit tests for readability-lite article extraction."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mining_news_mcp.extract import extract_article

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_extracts_title_text_and_publication_time() -> None:
    html = (FIXTURES / "sample_article.html").read_text(encoding="utf-8")
    article = extract_article(html, "https://demo.example/news/a")

    assert article.title == "Pilbara lithium shipments rise as prices stabilise"
    assert "Western Australian lithium producers" in article.text
    assert article.published_at == datetime(2025, 10, 1, 8, 30, tzinfo=UTC)


def test_strips_boilerplate_and_scripts() -> None:
    html = (FIXTURES / "sample_article.html").read_text(encoding="utf-8")
    article = extract_article(html, "https://demo.example/news/a")

    assert "Subscribe to our newsletter" not in article.text
    assert "should be stripped" not in article.text
    assert "All rights reserved" not in article.text
    assert "Related: Iron ore steady" not in article.text
    # Only the three real paragraphs remain.
    assert len(article.text.split("\n\n")) == 3


def test_falls_back_when_no_semantic_container() -> None:
    html = (
        "<html><head><title>Plain page</title></head><body><div>"
        "<p>" + "Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 3 + "</p>"
        "<p>" + "Sed do eiusmod tempor incididunt ut labore et dolore magna. " * 3 + "</p>"
        "</div></body></html>"
    )
    article = extract_article(html, "https://demo.example/plain")
    assert article.title == "Plain page"
    assert "Lorem ipsum" in article.text


def test_reads_ld_json_publication_date() -> None:
    html = (
        "<html><head>"
        '<script type="application/ld+json">'
        '{"@type": "NewsArticle", "datePublished": "2025-09-15T01:02:03+08:00"}'
        "</script></head><body><article><p>"
        + "Body paragraph long enough to count as real content here. " * 4
        + "</p></article></body></html>"
    )
    article = extract_article(html, "https://demo.example/ld")
    assert article.published_at == datetime(2025, 9, 14, 17, 2, 3, tzinfo=UTC)
