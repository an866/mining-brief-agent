"""Agent-layer models: plan, evidence bundle, narration, and final result.

The evidence bundle is the single source of truth the composer and narrators
read from — everything in the final Markdown must be derivable from it, and
the bundled citation list is what makes that checkable by a human.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from lme_price_mcp.models import TrendSeries
from mineral_pdf_mcp.models import ExtractionResult
from mining_news_mcp.models import Article, ArticleDetail


class RiskItem(BaseModel):
    severity: Literal["high", "medium", "info"]
    title: str
    detail: str
    citation_refs: list[int] = Field(
        default_factory=list,
        description="Indices into BriefEvidence.citations supporting this item.",
    )
    source: Literal["rule", "llm"] = "rule"


class Citation(BaseModel):
    index: int
    label: str
    url: str | None = None
    kind: Literal["news", "article", "report", "dataset"]


class BriefPlanInfo(BaseModel):
    project_key: str
    project_name: str
    project_name_en: str
    matched_alias: str | None = None
    commodities: list[str] = Field(default_factory=list)


class BriefEvidence(BaseModel):
    query: str
    days: int
    plan: BriefPlanInfo
    news: list[Article] = Field(default_factory=list)
    articles: list[ArticleDetail] = Field(default_factory=list)
    resources: ExtractionResult | None = None
    resource_uri: str | None = None
    trends: list[TrendSeries] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    data_modes: dict[str, str] = Field(
        default_factory=dict, description="Channel actually used per section: live / snapshot / ..."
    )
    warnings: list[str] = Field(default_factory=list)


class Narration(BaseModel):
    summary_md: str
    extra_risks_md: str | None = None
    mode: str = Field(description="'template', 'anthropic', or why it degraded.")


class BriefResult(BaseModel):
    markdown: str
    evidence: BriefEvidence
    narration: Narration
    generated_at: datetime
