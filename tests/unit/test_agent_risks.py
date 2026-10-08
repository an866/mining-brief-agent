"""Determinism tests for the rule-based risk scan (agent._inferred_share)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mineral_pdf_mcp.models import ExtractionResult, ResourceEstimate
from mining_brief_agent.agent import _inferred_share
from mining_brief_agent.models import BriefEvidence, BriefPlanInfo

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _row(category: str, tonnage: float, commodity: str = "Li2O") -> ResourceEstimate:
    return ResourceEstimate(
        category=category,
        commodity=commodity,
        tonnage_mt=tonnage,
        page=1,
        evidence=f"{category} {tonnage}",
        confidence=1.0,
    )


def _evidence(estimates: list[ResourceEstimate]) -> BriefEvidence:
    return BriefEvidence(
        query="q",
        days=7,
        plan=BriefPlanInfo(project_key="p", project_name="P", project_name_en="P", commodities=[]),
        resources=ExtractionResult(
            source="s",
            resolved_path="s",
            sha256="0" * 64,
            page_count=1,
            estimates=estimates,
            method="table",
            generated_at=NOW,
        ),
    )


def test_prefers_measured_and_indicated_row_as_denominator() -> None:
    rows = [
        _row("Measured", 18.2),
        _row("Indicated", 52.4),
        _row("Measured & Indicated", 70.6),
        _row("Inferred", 34.8),
    ]
    share = _inferred_share(_evidence(rows))
    assert share == pytest.approx(34.8 / (70.6 + 34.8))


def test_order_independent() -> None:
    rows = [
        _row("Measured", 18.2),
        _row("Indicated", 52.4),
        _row("Measured & Indicated", 70.6),
        _row("Inferred", 34.8),
    ]
    forward = _inferred_share(_evidence(rows))
    backward = _inferred_share(_evidence(list(reversed(rows))))
    assert forward == pytest.approx(backward)


def test_sums_measured_and_indicated_when_no_combined_row() -> None:
    rows = [_row("Measured", 10.0), _row("Indicated", 30.0), _row("Inferred", 20.0)]
    assert _inferred_share(_evidence(rows)) == pytest.approx(20.0 / 60.0)


def test_uses_largest_row_per_category() -> None:
    """Zone-level duplicate rows must not inflate the denominator."""
    rows = [
        _row("Indicated", 10.0),
        _row("Indicated", 50.0),
        _row("Inferred", 20.0),
    ]
    assert _inferred_share(_evidence(rows)) == pytest.approx(20.0 / 70.0)


def test_returns_none_without_inferred() -> None:
    assert _inferred_share(_evidence([_row("Indicated", 30.0)])) is None


def test_returns_none_without_confident_side() -> None:
    assert _inferred_share(_evidence([_row("Inferred", 30.0)])) is None
