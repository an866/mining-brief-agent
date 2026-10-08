"""Markdown composition and citation management.

The composer owns two responsibilities:

* :func:`build_citations` assigns stable ``[n]`` indices to every source the
  brief uses (news URLs, fetched articles, the NI 43-101 document, the price
  dataset). Indices are assigned *before* narration so both the narrators and
  the final Markdown refer to the same numbers.
* :func:`compose` renders the final Markdown report from the evidence bundle —
  the evidence is the only input, so every claim in the report is traceable to
  a numbered source.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import BriefEvidence, Citation, Narration, RiskItem

BEIJING = timezone(timedelta(hours=8))

SEVERITY_LABEL = {"high": "🔴 高", "medium": "🟠 中", "info": "⚪ 提示"}

_CATEGORY_ORDER = [
    "Measured",
    "Measured & Indicated",
    "Indicated",
    "Inferred",
    "Proven",
    "Probable",
    "Total",
]

_MODE_LABEL = {
    "snapshot": "离线快照（演示数据）",
    "live": "实时抓取",
    "snapshot+live": "快照历史 + 实时最新价",
    "local": "本地文档",
    "error": "获取失败",
}

_SECTION_MODE_NAMES = {"news": "新闻", "prices": "价格", "resources": "储量"}


def build_citations(evidence: BriefEvidence) -> list[Citation]:
    """Assign [n] indices in order of first appearance; URLs never duplicate."""
    citations: list[Citation] = []
    seen_urls: set[str] = set()

    def add(label: str, url: str | None, kind: str) -> None:
        if url is not None and url in seen_urls:
            return
        citations.append(
            Citation(index=len(citations) + 1, label=label[:90], url=url, kind=kind)  # type: ignore[arg-type]
        )
        if url is not None:
            seen_urls.add(url)

    for item in evidence.news:
        add(item.title, item.url, "news")
    for article in evidence.articles:
        add(article.article.title, article.article.url, "article")
    if evidence.resources is not None:
        label = evidence.resources.project_name or "NI 43-101 技术报告"
        add(f"NI 43-101 报告：{label}（{evidence.resource_uri}）", None, "report")
    if evidence.trends:
        channels = sorted({trend.provider for trend in evidence.trends})
        add(f"价格数据（{'/'.join(channels)} 通道）", None, "dataset")
    return citations


def ref_for_url(citations: list[Citation], url: str) -> str:
    return "".join(f"[{c.index}]" for c in citations if c.url == url)


def ref_indices_for_kind(citations: list[Citation], kind: str, limit: int = 2) -> list[int]:
    return [c.index for c in citations if c.kind == kind][:limit]


def _render_citation_refs(indices: list[int]) -> str:
    return "".join(f"[{i}]" for i in indices)


def compose(evidence: BriefEvidence, narration: Narration, generated_at: datetime) -> str:
    """Render the final Markdown brief."""
    lines: list[str] = []
    plan = evidence.plan

    local_time = generated_at.astimezone(BEIJING)
    lines.append(f"# 矿权日报 · {plan.project_name}")
    lines.append("")
    mode_summary = " ｜ ".join(
        f"{_SECTION_MODE_NAMES.get(section, section)}={_MODE_LABEL.get(mode, mode)}"
        for section, mode in evidence.data_modes.items()
    )
    lines.append(
        f"> 生成时间：{local_time:%Y-%m-%d %H:%M}（北京时间） ｜ 检索窗口：近{evidence.days}天"
        + (f" ｜ 数据通道：{mode_summary}" if mode_summary else "")
    )
    if plan.matched_alias:
        lines.append(
            f"> 项目识别：匹配别名“{plan.matched_alias}”；商品：{', '.join(plan.commodities) or '—'}"
        )
    lines.append("")

    lines.append("## 摘要")
    lines.append("")
    lines.append(narration.summary_md or "- （无）")
    lines.append("")

    lines.append("## 新闻速览")
    lines.append("")
    if evidence.news:
        for position, item in enumerate(evidence.news, start=1):
            ref = ref_for_url(evidence.citations, item.url)
            lines.append(
                f"{position}. **{item.title}** — {item.source} · {item.published_at:%Y-%m-%d} {ref}"
            )
            if item.summary:
                lines.append(f"   - {item.summary[:120]}")
        if evidence.articles:
            lines.append("")
            lines.append("### 全文参考")
            lines.append("")
            for article in evidence.articles:
                ref = ref_for_url(evidence.citations, article.article.url)
                excerpt = article.text.strip().replace("\n", " ")[:300]
                lines.append(
                    f"> 《{article.article.title}》{ref}"
                    f"（{article.via}，{article.word_count} 词）：{excerpt}…"
                )
    else:
        lines.append("（窗口内无匹配新闻）")
    lines.append("")

    lines.append("## 储量数据（NI 43-101）")
    lines.append("")
    estimates = evidence.resources.estimates if evidence.resources else []
    if estimates:
        report_refs = _render_citation_refs(
            ref_indices_for_kind(evidence.citations, "report", limit=1)
        )
        lines.append("| 类别 | 矿石量 (Mt) | 品位 | 金属量 | 来源 |")
        lines.append("| --- | ---: | --- | ---: | --- |")
        ordered = sorted(
            estimates,
            key=lambda e: (
                _CATEGORY_ORDER.index(e.category)
                if e.category in _CATEGORY_ORDER
                else len(_CATEGORY_ORDER),
                e.commodity,
            ),
        )
        for estimate in ordered:
            tonnage = f"{estimate.tonnage_mt:,.1f}" if estimate.tonnage_mt is not None else "—"
            grade = (
                f"{estimate.grade:g} {estimate.grade_unit or ''} {estimate.commodity}".strip()
                if estimate.grade is not None
                else estimate.commodity
            )
            contained = (
                f"{estimate.contained_metal:,.0f} {estimate.contained_unit or ''}".strip()
                if estimate.contained_metal is not None
                else "—"
            )
            lines.append(
                f"| {estimate.category} | {tonnage} | {grade} | {contained} "
                f"| {report_refs} p.{estimate.page} |"
            )
        assert evidence.resources is not None
        lines.append("")
        lines.append(
            f"*抽取方式：{evidence.resources.method}；每行的证据原句保存在证据包（`--json` 可导出），"
            f"文件 SHA-256 前12位：`{evidence.resources.sha256[:12]}`。*"
        )
    else:
        lines.append("（未解析到资源量数据）")
    lines.append("")

    lines.append(f"## 价格走势（近{evidence.trends[0].days if evidence.trends else 30}日）")
    lines.append("")
    if evidence.trends:
        dataset_refs = _render_citation_refs(ref_indices_for_kind(evidence.citations, "dataset"))
        lines.append("| 品种 | 最新价 | 窗口涨跌 | 方向 | 走势 |")
        lines.append("| --- | ---: | ---: | :-: | --- |")
        direction_zh = {"up": "↗ 上行", "down": "↘ 下行", "flat": "→ 持平"}
        for trend in evidence.trends:
            lines.append(
                f"| {trend.label} | {trend.latest.price:,.1f} {trend.unit} "
                f"| {trend.change_abs:+,.1f}（{trend.change_pct:+.2f}%） "
                f"| {direction_zh.get(trend.direction, trend.direction)} "
                f"| `{trend.sparkline}` |"
            )
        lines.append("")
        lines.append(f"*数据通道见页脚；最新价日期以各品种数据点为准。{dataset_refs}*")
    else:
        lines.append("（无价格数据）")
    lines.append("")

    lines.append("## 风险提示")
    lines.append("")
    if evidence.risks:
        for risk in evidence.risks:
            refs = _render_citation_refs(risk.citation_refs)
            lines.append(
                f"- {SEVERITY_LABEL.get(risk.severity, risk.severity)}｜**{risk.title}**："
                f"{risk.detail} {refs}".rstrip()
            )
    else:
        lines.append("- 未发现显著风险信号（仅代表本次窗口内的规则与数据判断）")
    if narration.extra_risks_md:
        lines.append("")
        lines.append("补充风险观察（Claude）：")
        lines.append(narration.extra_risks_md)
    lines.append("")
    lines.append(
        "> 免责声明：本简报由自动化管线生成，全部事实性内容附带引用编号；仅供研究参考，不构成任何投资建议。"
    )
    lines.append("")

    lines.append("## 引用源")
    lines.append("")
    if evidence.citations:
        for citation in evidence.citations:
            suffix = f" — {citation.url}" if citation.url else " —（仓库内演示数据）"
            lines.append(f"{citation.index}. {citation.label}{suffix}")
    else:
        lines.append("（无）")
    lines.append("")

    if evidence.warnings:
        lines.append("<details><summary>运行提示与降级记录</summary>")
        lines.append("")
        for warning in evidence.warnings:
            lines.append(f"- {warning}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append(
        f"*生成器：mining-brief-agent v0.1.0 ｜ 叙述模式：{narration.mode} ｜ "
        f"取证工具：mining-news-mcp / mineral-pdf-mcp / lme-price-mcp（MCP stdio）*"
    )
    return "\n".join(lines)


def severity_rank(risk: RiskItem) -> int:
    return {"high": 0, "medium": 1, "info": 2}[risk.severity]
