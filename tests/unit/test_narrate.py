"""Unit tests for the template narrator and the narration output parser."""

from __future__ import annotations

from datetime import UTC, datetime

from lme_price_mcp.models import PricePoint, TrendSeries
from mining_brief_agent.models import BriefEvidence, BriefPlanInfo
from mining_brief_agent.narrate import TemplateNarrator, _parse_narration, get_narrator
from mining_news_mcp.models import Article

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def _evidence() -> BriefEvidence:
    return BriefEvidence(
        query="q",
        days=7,
        plan=BriefPlanInfo(
            project_key="pilbara-lithium",
            project_name="Pilbara 锂矿（演示）",
            project_name_en="Pilbara Lithium Project (Demo)",
            commodities=["lithium_carbonate"],
        ),
        news=[
            Article(
                id="n-1",
                title="Pilbara shipments rise",
                url="https://demo.example/news/a",
                source="demo-wire",
                published_at=NOW,
                summary="",
            )
        ],
        trends=[
            TrendSeries(
                commodity="lithium_carbonate",
                label="Lithium carbonate",
                days=30,
                unit="CNY/t",
                points=[
                    PricePoint(
                        commodity="lithium_carbonate",
                        date=NOW.date(),
                        price=70000.0,
                        unit="CNY/t",
                    )
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
        data_modes={"news": "snapshot"},
    )


def test_template_narrator_uses_evidence_only() -> None:
    narration = TemplateNarrator().narrate(_evidence())
    assert narration.mode == "template"
    assert "Pilbara shipments rise" in narration.summary_md
    assert "-7.89%" in narration.summary_md
    assert "下行" in narration.summary_md
    assert "离线演示快照" in narration.summary_md
    assert narration.extra_risks_md is None


def test_template_narrator_without_news_says_so() -> None:
    evidence = _evidence()
    evidence.news = []
    narration = TemplateNarrator().narrate(evidence)
    assert "未检索到相关新闻" in narration.summary_md


def test_parse_narration_splits_sections_and_drops_leading_prose() -> None:
    text = (
        "好的，这是日报：\n"
        "[摘要]\n"
        "- 新闻面平稳 [1]\n"
        "价格下行 [3]\n"
        "[补充风险观察]\n"
        "- 锂价单周跌幅显著 [3]\n"
        "- \n"
    )
    summary, risks = _parse_narration(text)
    assert summary == "- 新闻面平稳 [1]\n- 价格下行 [3]"
    assert risks == "- 锂价单周跌幅显著 [3]"


def test_parse_narration_empty_risks_returns_none() -> None:
    summary, risks = _parse_narration("[摘要]\n- 只有摘要 [1]\n[补充风险观察]\n")
    assert summary == "- 只有摘要 [1]"
    assert risks is None


def test_get_narrator_auto_uses_template_without_sdk(monkeypatch) -> None:
    import mining_brief_agent.narrate as narrate_module

    monkeypatch.setattr(narrate_module, "_module_available", lambda name: False)
    assert type(narrate_module.get_narrator("auto")).__name__ == "TemplateNarrator"


def test_get_narrator_auto_uses_anthropic_with_sdk_and_credentials(monkeypatch) -> None:
    import mining_brief_agent.narrate as narrate_module

    monkeypatch.setattr(narrate_module, "_module_available", lambda name: True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert type(narrate_module.get_narrator("auto")).__name__ == "AnthropicNarrator"


def test_get_narrator_explicit_modes() -> None:
    assert type(get_narrator("template")).__name__ == "TemplateNarrator"
    assert type(get_narrator("anthropic")).__name__ == "AnthropicNarrator"
