"""Turn a natural-language query into a concrete brief plan.

Resolution is deliberately simple and transparent (no embeddings): aliases
from the project catalog are matched against the query with word boundaries
for ASCII aliases and substring matching for CJK, falling back to the
catalog's default project when nothing matches. Commodities come from the
project plus any commodity alias mentioned in the query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lme_price_mcp.commodities import COMMODITIES, CommoditySpec

from .catalog import Catalog, ProjectSpec, load_catalog

DEFAULT_NEWS_DAYS = 7


def _alias_matches(alias: str, query_lower: str) -> bool:
    if not alias:
        return False
    if alias.isascii():
        return re.search(rf"\b{re.escape(alias.lower())}\b", query_lower) is not None
    return alias in query_lower


@dataclass(frozen=True)
class BriefPlan:
    project: ProjectSpec
    commodities: tuple[CommoditySpec, ...]
    news_query: str
    days: int
    matched_alias: str | None = None
    notes: list[str] = field(default_factory=list)


def _match_project(catalog: Catalog, query_lower: str) -> tuple[ProjectSpec, str | None]:
    for project in catalog.projects:
        for alias in sorted(project.aliases, key=len, reverse=True):
            if _alias_matches(alias, query_lower):
                return project, alias
    return catalog.by_key(catalog.default_project), None


def _match_commodities(query_lower: str) -> list[CommoditySpec]:
    matched: list[CommoditySpec] = []
    for spec in COMMODITIES.values():
        if any(_alias_matches(alias, query_lower) for alias in spec.normalized_aliases):
            matched.append(spec)
    return matched


def resolve_query(
    query: str,
    days: int = DEFAULT_NEWS_DAYS,
    *,
    catalog: Catalog | None = None,
) -> BriefPlan:
    """Resolve a user query into a :class:`BriefPlan`."""
    active_catalog = catalog or load_catalog()
    query_lower = query.lower()

    project, matched_alias = _match_project(active_catalog, query_lower)

    notes: list[str] = []
    if matched_alias is None:
        notes.append(f"未在查询中识别出项目名称，使用默认项目 {project.display_name}")

    commodities: list[CommoditySpec] = []
    for key in project.commodities:
        spec = COMMODITIES.get(key)
        if spec is not None and spec not in commodities:
            commodities.append(spec)
    for spec in _match_commodities(query_lower):
        if spec not in commodities:
            commodities.append(spec)

    return BriefPlan(
        project=project,
        commodities=tuple(commodities),
        news_query=project.news_query,
        days=max(1, days),
        matched_alias=matched_alias,
        notes=notes,
    )
