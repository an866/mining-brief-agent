"""Narration for the brief's summary and risk sections.

Two implementations behind one interface:

* :class:`TemplateNarrator` — deterministic, dependency-free Chinese prose
  built directly from the evidence bundle. This is the default and the
  guaranteed fallback: the pipeline never *requires* an LLM.
* :class:`AnthropicNarrator` — optionally asks Claude (Opus 5 by default,
  ``MINING_BRIEF_LLM_MODEL`` overrides) to write the summary from the same
  evidence, with strict citation instructions. Any failure (missing SDK, no
  credentials, API error, refusal, unparsable output) degrades to the
  template narrator with the reason recorded in ``Narration.mode``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from .models import BriefEvidence, Narration

LLM_MODEL_ENV_VAR = "MINING_BRIEF_LLM_MODEL"
DEFAULT_LLM_MODEL = "claude-opus-5"

DIRECTION_ZH = {"up": "上行", "down": "下行", "flat": "持平"}

ANTHROPIC_SYSTEM_PROMPT = (
    "你是资深矿业分析师，为「矿权日报」撰写简短的中文叙述段落。严格执行以下规则：\n"
    "1. 只能使用用户提供的证据数据；绝不引入外部知识，绝不编造数字、事件或结论。\n"
    "2. 每个事实性断言必须在句末标注引用编号（例如 [1][3]），编号只能来自“引用源列表”。\n"
    "3. 输出格式必须严格遵守：\n"
    "[摘要]\n"
    "- 不超过3条要点，每条一句话，覆盖新闻动态、储量/资源、价格走势中最重要的信号。\n"
    "[补充风险观察]\n"
    "- 0到3条；仅在证据支持时才写（如价格显著下跌、Inferred 资源占比偏高、新闻中的负面信号）；没有足够证据则留空。\n"
    "4. 全部输出不超过 220 字。"
)

_MAX_DIGEST_CHARS = 8_000


class Narrator(Protocol):
    def narrate(self, evidence: BriefEvidence) -> Narration: ...


def _pct(value: float) -> str:
    return f"{value:+.2f}%"


class TemplateNarrator:
    """Deterministic evidence-to-prose, no network, no LLM."""

    def narrate(self, evidence: BriefEvidence) -> Narration:
        lines: list[str] = []

        window = f"近{evidence.days}天"
        if evidence.news:
            top = evidence.news[0]
            lines.append(
                f"{window}内检索到 {len(evidence.news)} 条相关新闻，最新一条为《{top.title}》"
                f"（{top.source}，{top.published_at:%Y-%m-%d}）"
            )
        else:
            lines.append(f"{window}内未检索到相关新闻")

        if evidence.resources and evidence.resources.estimates:
            highlights = _key_resource_highlights(evidence)
            if highlights:
                lines.append("NI 43-101 资源量：" + "；".join(highlights))

        for trend in evidence.trends:
            lines.append(
                f"{trend.label}最新价 {trend.latest.price:,.1f} {trend.unit}，"
                f"近{trend.days}日 {_pct(trend.change_pct)}"
                f"（{DIRECTION_ZH.get(trend.direction, trend.direction)}）"
            )

        snapshot_used = any("snapshot" in mode for mode in evidence.data_modes.values())
        if snapshot_used:
            lines.append("部分数据来自离线演示快照（非实时），详见页脚数据通道说明")

        return Narration(
            summary_md="\n".join(f"- {line}" for line in lines),
            extra_risks_md=None,
            mode="template",
        )


def _key_resource_highlights(evidence: BriefEvidence) -> list[str]:
    """One Indicated/M&I highlight and one Inferred highlight, if present."""
    assert evidence.resources is not None
    highlights: list[str] = []
    for wanted in (("Measured & Indicated", "Indicated"), ("Inferred",)):
        for estimate in evidence.resources.estimates:
            if estimate.category in wanted and estimate.tonnage_mt is not None:
                part = f"{estimate.category} {estimate.tonnage_mt:,.1f} Mt"
                if estimate.grade is not None and estimate.grade_unit:
                    part += f" @ {estimate.grade} {estimate.grade_unit} {estimate.commodity}"
                if estimate.contained_metal is not None and estimate.contained_unit:
                    part += f"（含 {estimate.contained_metal:,.0f} {estimate.contained_unit} {estimate.commodity}）"
                highlights.append(part)
                break
    return highlights


class AnthropicNarrator:
    """Ask Claude to write the summary; degrade to template on any failure."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or os.environ.get(LLM_MODEL_ENV_VAR, DEFAULT_LLM_MODEL)

    def narrate(self, evidence: BriefEvidence) -> Narration:
        try:
            import anthropic
        except ImportError:
            return self._fallback(
                evidence, "anthropic SDK 未安装（pip install 'mining-brief-agent[llm]'）"
            )

        digest = _build_digest(evidence)
        try:
            client = anthropic.Anthropic(timeout=120.0)
            response = self._create_message(client, digest)
            if getattr(response, "stop_reason", None) == "refusal":
                return self._fallback(evidence, "Claude 拒绝了该请求（stop_reason=refusal）")
            text = "".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            )
        except anthropic.APIError as exc:
            return self._fallback(evidence, f"Claude API 错误（{type(exc).__name__}）")
        except Exception as exc:
            return self._fallback(evidence, f"叙述器异常（{type(exc).__name__}: {exc}）")

        summary, risks = _parse_narration(text)
        if not summary:
            return self._fallback(evidence, "Claude 输出不符合约定格式")
        return Narration(summary_md=summary, extra_risks_md=risks, mode="anthropic")

    def _create_message(self, client: Any, digest: str) -> Any:
        """Prefer the beta endpoint with server-side refusal fallbacks; retry
        once on the plain endpoint if the beta parameter is rejected."""
        import anthropic

        kwargs: dict[str, object] = {
            "model": self._model,
            "max_tokens": 4000,
            "system": ANTHROPIC_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": digest}],
        }
        try:
            return client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                **kwargs,
            )
        except anthropic.BadRequestError:
            return client.messages.create(**kwargs)

    def _fallback(self, evidence: BriefEvidence, reason: str) -> Narration:
        template = TemplateNarrator().narrate(evidence)
        return Narration(
            summary_md=template.summary_md,
            extra_risks_md=template.extra_risks_md,
            mode=f"anthropic->template（{reason}）",
        )


def _build_digest(evidence: BriefEvidence) -> str:
    parts: list[str] = []
    plan = evidence.plan
    parts.append(
        f"项目: {plan.project_name} | {plan.project_name_en}；查询: {evidence.query}；窗口: 近{evidence.days}天"
    )

    if evidence.citations:
        parts.append("引用源列表:")
        for citation in evidence.citations:
            url = citation.url or "（仓库内演示数据）"
            parts.append(f"[{citation.index}] {citation.label} — {url}")

    if evidence.news:
        parts.append("新闻检索结果:")
        for item in evidence.news:
            refs = _refs_for_url(evidence, item.url)
            parts.append(
                f"- {item.title} | {item.source} | {item.published_at:%Y-%m-%d}"
                + (f" {refs}" if refs else "")
            )

    for article in evidence.articles:
        refs = _refs_for_url(evidence, article.article.url)
        excerpt = article.text[:400].replace("\n", " ")
        parts.append(f"- 全文摘录《{article.article.title}》{refs}: {excerpt}")

    if evidence.resources and evidence.resources.estimates:
        parts.append("NI 43-101 资源量（页码/引用）:")
        refs = _refs_for_kind(evidence, "report")
        for estimate in evidence.resources.estimates:
            line = f"- {estimate.category} {estimate.commodity}"
            if estimate.tonnage_mt is not None:
                line += f": {estimate.tonnage_mt:,.1f} Mt"
            if estimate.grade is not None and estimate.grade_unit:
                line += f" @ {estimate.grade} {estimate.grade_unit}"
            if estimate.contained_metal is not None and estimate.contained_unit:
                line += f"（含 {estimate.contained_metal:,.0f} {estimate.contained_unit}）"
            line += f" [pdf第{estimate.page}页]"
            if refs:
                line += f" {refs}"
            parts.append(line)

    for trend in evidence.trends:
        refs = _refs_for_kind(evidence, "dataset")
        parts.append(
            f"- 价格 {trend.label}: 最新 {trend.latest.price:,.1f} {trend.unit}；"
            f"近{trend.days}日 {_pct(trend.change_pct)}（{trend.direction}）"
            f"{trend.sparkline} {refs}"
        )

    if evidence.risks:
        parts.append("规则引擎初判风险:")
        for risk in evidence.risks:
            parts.append(f"- [{risk.severity}] {risk.title}: {risk.detail}")

    if evidence.data_modes:
        parts.append("数据通道: " + json.dumps(evidence.data_modes, ensure_ascii=False))

    digest = "\n".join(parts)
    return digest[:_MAX_DIGEST_CHARS]


def _refs_for_url(evidence: BriefEvidence, url: str) -> str:
    refs = [f"[{c.index}]" for c in evidence.citations if c.url == url]
    return "".join(refs)


def _refs_for_kind(evidence: BriefEvidence, kind: str) -> str:
    refs = [f"[{c.index}]" for c in evidence.citations if c.kind == kind]
    return "".join(refs[:2])


def _parse_narration(text: str) -> tuple[str, str | None]:
    """Split the model's output into (summary_md, extra_risks_md|None)."""
    summary_lines: list[str] = []
    risk_lines: list[str] = []
    section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[摘要]"):
            section = "summary"
            continue
        if line.startswith("[补充风险观察]"):
            section = "risks"
            continue
        if section == "summary":
            summary_lines.append(line if line.startswith("-") else f"- {line}")
        elif section == "risks" and line.startswith("-") and len(line) > 2:
            risk_lines.append(line)
    summary = "\n".join(summary_lines).strip()
    risks = "\n".join(risk_lines).strip() or None
    return summary, risks


def get_narrator(mode: str = "auto") -> Narrator:
    """``auto``: use Claude when the SDK and credentials are present."""
    if mode == "anthropic":
        return AnthropicNarrator()
    if mode == "template":
        return TemplateNarrator()
    if mode != "auto":
        raise ValueError(f"unknown narrator mode {mode!r} (use auto|template|anthropic)")

    has_sdk = _module_available("anthropic")
    has_credentials = bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )
    if has_sdk and has_credentials:
        return AnthropicNarrator()
    return TemplateNarrator()


def _module_available(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False
