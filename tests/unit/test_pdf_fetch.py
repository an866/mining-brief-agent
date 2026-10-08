"""Unit tests for PDF source resolution (path / file:// / validation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mineral_pdf_mcp.fetch import resolve_pdf_source
from mining_brief_core.errors import FetchError
from scripts.make_sample_pdf import build_all


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_all(tmp_path_factory.mktemp("samples"))["pilbara_lithium"]


def test_resolves_absolute_path(sample_pdf: Path) -> None:
    path, downloaded = resolve_pdf_source(str(sample_pdf))
    assert path == sample_pdf
    assert downloaded is False


def test_resolves_file_uri(sample_pdf: Path) -> None:
    path, _ = resolve_pdf_source(sample_pdf.as_uri())
    assert path == sample_pdf


def test_rejects_non_pdf_content(tmp_path: Path) -> None:
    fake = tmp_path / "report.pdf"
    fake.write_text(json.dumps({"not": "a pdf"}), encoding="utf-8")
    with pytest.raises(FetchError, match="%PDF"):
        resolve_pdf_source(str(fake))


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="not found"):
        resolve_pdf_source(str(tmp_path / "missing.pdf"))


def test_rejects_unsupported_scheme() -> None:
    with pytest.raises(FetchError, match="unsupported URI scheme"):
        resolve_pdf_source("ftp://example.com/report.pdf")
