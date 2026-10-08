"""Unit tests for natural-language query planning."""

from __future__ import annotations

from mining_brief_agent.planning import resolve_query

DEMO_QUERY = "给我生成一份关于 Pilbara 锂矿的今日简报"


def test_resolves_demo_query_to_pilbara_project() -> None:
    plan = resolve_query(DEMO_QUERY)
    assert plan.project.key == "pilbara-lithium"
    assert plan.matched_alias == "pilbara"
    assert [spec.key for spec in plan.commodities] == ["lithium_carbonate"]
    assert plan.news_query == "Pilbara Pilgangoora lithium"


def test_resolves_chinese_alias() -> None:
    plan = resolve_query("皮尔巴拉矿区有什么新闻")
    assert plan.project.key == "pilbara-lithium"
    assert plan.matched_alias == "皮尔巴拉"


def test_resolves_second_project() -> None:
    plan = resolve_query("安第斯铜金矿现在什么情况")
    assert plan.project.key == "andes-copper-gold"
    assert [spec.key for spec in plan.commodities] == ["copper"]


def test_unknown_query_falls_back_to_default_with_note() -> None:
    plan = resolve_query("给我看看今天的行情")
    assert plan.project.key == "pilbara-lithium"
    assert plan.matched_alias is None
    assert plan.notes  # the fallback is announced, never silent


def test_commodity_scan_adds_commodities_from_query() -> None:
    plan = resolve_query("碳酸锂和铜的价格怎么样")
    keys = [spec.key for spec in plan.commodities]
    assert "lithium_carbonate" in keys
    assert "copper" in keys


def test_short_ascii_aliases_need_word_boundaries() -> None:
    """'cu' must not match inside ordinary words like 'document'."""
    plan = resolve_query("show me the document summary")
    assert [spec.key for spec in plan.commodities] == ["lithium_carbonate"]  # project default only


def test_days_are_clamped() -> None:
    assert resolve_query("pilbara", days=0).days == 1
