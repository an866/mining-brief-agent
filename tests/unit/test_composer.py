"""Unit tests for Markdown composition and citation management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lme_price_mcp.models import PricePoint, TrendSeries
from mineral_pdf_mcp.models import ExtractionResult, ResourceEstimate
from mining_brief_agent.composer import build_citations, compose
from mining_brief_agent.models import (
    BriefEvidence,
    BriefPlanInfo,
    Narration,
    RiskItem,
)
from mining_news_mcp.models import Article

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _evidence() -> BriefEvidence:
    return BriefEvidence(
        query="给我生成一份关于 Pilbara 锂矿的今日简报",
        days=7,
        plan=BriefPlanInfo(
            project_key="pilbara-lithium",
            project_name="Pilbara 锂矿（演示）",
            project_name_en="Pilbara Lithium Project (Demo)",
            matched_alias="pilbara",
            commodities=["lithium_carbonate"],
        ),
        news=[
            Article(
                id="n-0001",
                title="Pilbara shipments rise",
                url="https://demo.example/news/a",
                source="demo-wire",
                published_at=NOW - timedelta(days=1),
                summary="Shipments rose.",
            )
        ],
        resources=ExtractionResult(
            source="data/samples/pilbara_li2o_ni43101_sample.pdf",
            resolved_path="data/samples/pilbara_li2o_ni43101_sample.pdf",
            sha256="0" * 64,
            page_count=2,
            project_name="Pilbara Lithium Project (Demo)",
            estimates=[
                ResourceEstimate(
                    category="Indicated",
                    commodity="Li2O",
                    tonnage_mt=52.4,
                    grade=1.12,
                    grade_unit="%",
                    contained_metal=587,
                    contained_unit="kt",
                    page=2,
                    evidence="Indicated | 52.4 | 1.12 | 587",
                    confidence=1.0,
                ),
                ResourceEstimate(
                    category="Inferred",
                    commodity="Li2O",
                    tonnage_mt=34.8,
                    grade=0.94,
                    grade_unit="%",
                    contained_metal=327,
                    contained_unit="kt",
                    page=2,
                    evidence="Inferred | 34.8 | 0.94 | 327",
                    confidence=1.0,
                ),
            ],
            method="table",
            generated_at=NOW,
        ),
        resource_uri="data/samples/pilbara_li2o_ni43101_sample.pdf",
        trends=[
            TrendSeries(
                commodity="lithium_carbonate",
                label="Lithium carbonate (GFEX main contract)",
                days=30,
                unit="CNY/t",
                points=[
                    PricePoint(
                        commodity="lithium_carbonate",
                        date=NOW.date() - timedelta(days=1),
                        price=76000.0,
                        unit="CNY/t",
                    ),
                    PricePoint(
                        commodity="lithium_carbonate", date=NOW.date(), price=70000.0, unit="CNY/t"
                    ),
                ],
                latest=PricePoint(
                    commodity="lithium_carbonate", date=NOW.date(), price=70000.0, unit="CNY/t"
                ),
                change_abs=-6000.0,
                change_pct=-7.89,
                direction="down",
                sparkline="▇▁",
                provider="snapshot",
                fetched_at=NOW,
            )
        ],
        data_modes={"news": "snapshot", "resources": "local", "prices": "snapshot"},
    )


def test_build_citations_dedupes_by_url_and_orders_first_use() -> None:
    evidence = _evidence()
    citations = build_citations(evidence)
    kinds = [c.kind for c in citations]
    assert kinds == ["news", "report", "dataset"]
    assert citations[0].url == "https://demo.example/news/a"
    assert [c.index for c in citations] == [1, 2, 3]


def test_compose_contains_all_required_sections_in_order() -> None:
    evidence = _evidence()
    evidence.citations = build_citations(evidence)
    markdown = compose(evidence, Narration(summary_md="- 测试摘要", mode="template"), NOW)
    positions = [
        markdown.index("## 摘要"),
        markdown.index("## 新闻速览"),
        markdown.index("## 储量数据"),
        markdown.index("## 价格走势"),
        markdown.index("## 风险提示"),
        markdown.index("## 引用源"),
    ]
    assert positions == sorted(positions)
    assert markdown.startswith("# 矿权日报 · Pilbara 锂矿（演示）")
    assert "52.4" in markdown and "1.12 % Li2O" in markdown
    assert "-6,000.0" in markdown and "-7.89%" in markdown
    assert "[1]" in markdown  # news citation
    assert "免责声明" in markdown
    assert "https://demo.example/news/a" in markdown  # citation list carries the link


def test_compose_renders_risks_with_severity_and_refs() -> None:
    evidence = _evidence()
    evidence.citations = build_citations(evidence)
    evidence.risks = [
        RiskItem(
            severity="high",
            title="价格显著下行",
            detail="近30日 -7.89%。",
            citation_refs=[3],
        )
    ]
    markdown = compose(evidence, Narration(summary_md="- 摘要", mode="template"), NOW)
    assert "🔴 高｜**价格显著下行**" in markdown
    assert "[3]" in markdown


def test_compose_handles_missing_data_gracefully() -> None:
    evidence = BriefEvidence(
        query="q",
        days=7,
        plan=BriefPlanInfo(
            project_key="p", project_name="P", project_name_en="P-EN", commodities=[]
        ),
        data_modes={"news": "error"},
        warnings=["news 获取失败：boom"],
    )
    markdown = compose(evidence, Narration(summary_md="-", mode="template"), NOW)
    assert "（窗口内无匹配新闻）" in markdown
    assert "（未解析到资源量数据）" in markdown
    assert "（无价格数据）" in markdown
    assert "news 获取失败：boom" in markdown
