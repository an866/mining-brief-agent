"""Brief orchestrator: plan → parallel evidence gathering over MCP → rule-based
risk scan → narration → Markdown composition.

Everything the report contains flows through :class:`BriefEvidence`; the
gather stage tolerates individual sources failing (recording an ``error``
channel and a warning) so one dead feed never leaves the operator without a
brief.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from lme_price_mcp.models import TrendSeries
from mineral_pdf_mcp.models import ExtractionResult
from mining_news_mcp.models import Article, ArticleDetail, SearchResult

from .composer import build_citations, compose, ref_indices_for_kind, severity_rank
from .mcp_client import NEWS_SERVER, PDF_SERVER, PRICE_SERVER, ServerHub
from .models import BriefEvidence, BriefPlanInfo, BriefResult, RiskItem
from .narrate import get_narrator
from .planning import BriefPlan, resolve_query

TREND_DAYS = 30
MAX_RISKS = 8

_HARD_KEYWORDS = {
    "halt",
    "halted",
    "outage",
    "lawsuit",
    "court",
    "strike",
    "suspension",
    "停产",
    "诉讼",
    "事故",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def run_brief(
    query: str,
    *,
    days: int = 7,
    top_news: int = 5,
    fetch_top: int = 2,
    narrator: str = "auto",
    offline: bool = False,
) -> BriefResult:
    """Generate a complete brief for ``query``."""
    plan = resolve_query(query, days=days)

    evidence = BriefEvidence(
        query=query,
        days=plan.days,
        plan=BriefPlanInfo(
            project_key=plan.project.key,
            project_name=plan.project.display_name,
            project_name_en=plan.project.name_en,
            matched_alias=plan.matched_alias,
            commodities=[spec.key for spec in plan.commodities],
        ),
        warnings=list(plan.notes),
    )

    env_overrides: dict[str, str] = {}
    if offline:
        env_overrides = {
            "MINING_NEWS_SOURCE": "snapshot",
            "MINING_PRICE_SOURCE": "snapshot",
        }

    async with ServerHub(env_overrides=env_overrides) as hub:
        await _gather(hub, plan, evidence, top_news=top_news, fetch_top=fetch_top)

    evidence.citations = build_citations(evidence)
    evidence.risks = _derive_risks(evidence, plan.project.risk_keywords)
    narration = get_narrator(narrator).narrate(evidence)
    generated_at = _utcnow()
    markdown = compose(evidence, narration, generated_at)
    return BriefResult(
        markdown=markdown,
        evidence=evidence,
        narration=narration,
        generated_at=generated_at,
    )


async def _gather(
    hub: ServerHub,
    plan: BriefPlan,
    evidence: BriefEvidence,
    *,
    top_news: int,
    fetch_top: int,
) -> None:
    tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}

    tasks["news"] = asyncio.create_task(
        hub.call_tool(
            NEWS_SERVER, "search", {"query": plan.news_query, "days": plan.days, "limit": top_news}
        )
    )

    resource_doc = plan.project.resources[0] if plan.project.resources else None
    if resource_doc is not None:
        evidence.resource_uri = resource_doc.uri
        tasks["resources"] = asyncio.create_task(
            hub.call_tool(PDF_SERVER, "extract_resources", {"pdf_url": resource_doc.uri})
        )

    for spec in plan.commodities:
        tasks[f"price:{spec.key}"] = asyncio.create_task(
            hub.call_tool(PRICE_SERVER, "get_trend", {"commodity": spec.key, "days": TREND_DAYS})
        )

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for key, result in zip(tasks.keys(), results, strict=True):
        section = key.split(":", 1)[0]
        if isinstance(result, BaseException):
            evidence.data_modes[section] = "error"
            evidence.warnings.append(f"{key} 获取失败：{result}")
            continue

        if key == "news":
            parsed = SearchResult.model_validate(result)
            evidence.news = parsed.items[:top_news]
            evidence.data_modes["news"] = parsed.provider
            evidence.warnings.extend(parsed.notes)
        elif key == "resources":
            evidence.resources = ExtractionResult.model_validate(result)
            evidence.data_modes["resources"] = "local" if evidence.resource_uri else "error"
            evidence.warnings.extend(evidence.resources.warnings)
        elif key.startswith("price:"):
            trend = TrendSeries.model_validate(result)
            evidence.trends.append(trend)
            evidence.data_modes["prices"] = trend.provider
            evidence.warnings.extend(trend.notes)

    await _fetch_top_articles(hub, evidence, fetch_top)


async def _fetch_top_articles(hub: ServerHub, evidence: BriefEvidence, fetch_top: int) -> None:
    targets = evidence.news[: max(0, fetch_top)]
    if not targets:
        return
    tasks = {
        item.url: asyncio.create_task(
            hub.call_tool(NEWS_SERVER, "fetch_article", {"url": item.url})
        )
        for item in targets
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for url, result in zip(tasks.keys(), results, strict=True):
        if isinstance(result, BaseException):
            evidence.warnings.append(f"fetch_article({url}) 失败：{result}")
            continue
        evidence.articles.append(ArticleDetail.model_validate(result))


def _derive_risks(evidence: BriefEvidence, risk_keywords: list[str]) -> list[RiskItem]:
    risks: list[RiskItem] = []
    dataset_refs = ref_indices_for_kind(evidence.citations, "dataset")

    for trend in evidence.trends:
        if trend.change_pct <= -5:
            risks.append(
                RiskItem(
                    severity="high",
                    title=f"{trend.label}价格显著下行",
                    detail=(
                        f"近{trend.days}日 {trend.change_pct:+.2f}%（最新 {trend.latest.price:,.1f} "
                        f"{trend.unit}），对项目经济性构成压力。"
                    ),
                    citation_refs=dataset_refs,
                )
            )
        elif trend.change_pct <= -2:
            risks.append(
                RiskItem(
                    severity="medium",
                    title=f"{trend.label}价格走弱",
                    detail=f"近{trend.days}日 {trend.change_pct:+.2f}%，关注后续走势。",
                    citation_refs=dataset_refs,
                )
            )
        elif trend.change_pct >= 8:
            risks.append(
                RiskItem(
                    severity="info",
                    title=f"{trend.label}价格快速上行",
                    detail=f"近{trend.days}日 {trend.change_pct:+.2f}%，注意成本与采购节奏。",
                    citation_refs=dataset_refs,
                )
            )

    if evidence.resources is not None and evidence.resources.estimates:
        report_refs = ref_indices_for_kind(evidence.citations, "report")
        share = _inferred_share(evidence)
        if share is not None:
            if share >= 0.5:
                risks.append(
                    RiskItem(
                        severity="medium",
                        title="Inferred 资源占比较高",
                        detail=f"Inferred 占已披露资源总量约 {share:.0%}，地质置信度相对较低。",
                        citation_refs=report_refs,
                    )
                )
            elif share >= 0.35:
                risks.append(
                    RiskItem(
                        severity="info",
                        title="Inferred 资源占比",
                        detail=f"Inferred 占已披露资源总量约 {share:.0%}，建议关注后续升级钻探。",
                        citation_refs=report_refs,
                    )
                )
        low_confidence = [e for e in evidence.resources.estimates if e.confidence < 1.0]
        if low_confidence:
            risks.append(
                RiskItem(
                    severity="info",
                    title="部分储量行来自文字抽取",
                    detail=(
                        f"{len(low_confidence)} 行资源量出自正文语句而非表格，已标注较低置信度，"
                        "建议人工复核证据句。"
                    ),
                    citation_refs=report_refs,
                )
            )
    else:
        risks.append(
            RiskItem(
                severity="info",
                title="缺少 NI 43-101 资源量数据",
                detail="本次未解析到资源量表格，储量相关结论暂缺。",
            )
        )

    hits: list[tuple[Article, str]] = []
    for item in evidence.news:
        haystack = f"{item.title} {item.summary}".lower()
        hit = next((kw for kw in risk_keywords if kw.lower() in haystack), None)
        if hit is not None:
            hits.append((item, hit))
    for item, keyword in hits[:3]:
        url_refs = [c.index for c in evidence.citations if c.url == item.url]
        risks.append(
            RiskItem(
                severity="high" if keyword.lower() in _HARD_KEYWORDS else "medium",
                title=f"新闻信号：{item.title[:36]}{'…' if len(item.title) > 36 else ''}",
                detail=f"命中风险关键词「{keyword}」（{item.source} · {item.published_at:%Y-%m-%d}）。",
                citation_refs=url_refs,
            )
        )

    if any("snapshot" in mode for mode in evidence.data_modes.values()):
        risks.append(
            RiskItem(
                severity="info",
                title="部分数据为离线演示快照",
                detail="本次运行有数据通道回落到仓库内置快照（合成演示数据），非实时行情/真实语料。",
            )
        )

    risks.sort(key=severity_rank)
    return risks[:MAX_RISKS]


def _inferred_share(evidence: BriefEvidence) -> float | None:
    """Inferred tonnage share for the first commodity that has both groups."""
    assert evidence.resources is not None
    by_commodity: dict[str, dict[str, float]] = {}
    for estimate in evidence.resources.estimates:
        if estimate.tonnage_mt is None:
            continue
        if estimate.category == "Inferred":
            group = "inferred"
        elif estimate.category in ("Measured", "Indicated", "Measured & Indicated"):
            group = "confident"
        else:
            continue
        by_commodity.setdefault(estimate.commodity, {}).setdefault(group, estimate.tonnage_mt)
    for groups in by_commodity.values():
        inferred = groups.get("inferred")
        confident = groups.get("confident")
        if inferred and confident and (inferred + confident) > 0:
            return inferred / (inferred + confident)
    return None
