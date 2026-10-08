"""End-to-end test: the full agent pipeline over real MCP stdio subprocesses.

Runs the demo query in offline mode (snapshot channels) so the test is
deterministic and network-free while still exercising every real component:
three spawned MCP servers, protocol handshakes, tool calls, PDF extraction,
trend analytics, risk rules, narration and composition.
"""

from __future__ import annotations

import asyncio

import pytest

from mining_brief_agent.agent import run_brief
from mining_brief_agent.cli import DEFAULT_QUERY

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def brief():
    return asyncio.run(run_brief(DEFAULT_QUERY, offline=True, narrator="template"))


def test_report_sections_present_in_order(brief) -> None:
    markdown = brief.markdown
    for section in (
        "# 矿权日报",
        "## 摘要",
        "## 新闻速览",
        "## 储量数据（NI 43-101）",
        "## 价格走势",
        "## 风险提示",
        "## 引用源",
        "免责声明",
    ):
        assert section in markdown, f"missing section: {section}"
    positions = [
        markdown.index("## 摘要"),
        markdown.index("## 新闻速览"),
        markdown.index("## 储量数据"),
        markdown.index("## 价格走势"),
        markdown.index("## 风险提示"),
        markdown.index("## 引用源"),
    ]
    assert positions == sorted(positions)


def test_resource_table_reflects_demo_pdf(brief) -> None:
    markdown = brief.markdown
    assert "52.4" in markdown  # Indicated tonnage from the sample PDF
    assert "1.12 % Li2O" in markdown
    assert "587 kt" in markdown
    assert brief.evidence.resources is not None
    assert brief.evidence.resources.method in ("table", "table+text")


def test_news_and_prices_come_from_snapshot_channel(brief) -> None:
    assert brief.evidence.data_modes.get("news") == "snapshot"
    assert brief.evidence.data_modes.get("prices", "").startswith("snapshot")
    assert brief.evidence.data_modes.get("resources") == "local"
    assert len(brief.evidence.news) >= 3
    assert len(brief.evidence.articles) >= 1  # full text fetched for the top item
    assert "https://demo.example/news/" in brief.markdown


def test_citations_and_risks_wired_up(brief) -> None:
    indices = [c.index for c in brief.evidence.citations]
    assert indices == list(range(1, len(indices) + 1))
    assert any(c.kind == "report" for c in brief.evidence.citations)
    assert any(c.kind == "dataset" for c in brief.evidence.citations)
    assert brief.evidence.risks, "rule engine should surface at least the snapshot notice"
    assert all(risk.title for risk in brief.evidence.risks)


def test_no_error_markers_in_report(brief) -> None:
    assert "获取失败" not in brief.markdown
    assert "Traceback" not in brief.markdown
