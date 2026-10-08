"""NI 43-101 mineral-resource extraction from PDF text and tables.

Two complementary strategies, merged with table results preferred:

1. **Table mode** — ``pdfplumber.extract_tables()`` finds resource-statement
   tables (header row mentions categories plus tonnage/grade/contained
   columns) and maps each column to a field by its header text. This is the
   high-confidence path (confidence 1.0) and generalises across commodities
   because grade/contained columns are grouped *per commodity symbol* found in
   the header ('Cu %', 'Au g/t', 'Contained Li2O (kt)' ...).
2. **Text mode** — line-level regexes for prose statements such as
   ``"Indicated Resources of 52.4 Mt at 1.02 % Cu for 534 kt Cu"``
   (confidence 0.7). Used when a report states resources in running text
   instead of a table.

Rows that mention a category but expose no tonnage are reported as warnings
rather than silently dropped.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import pdfplumber
from pdfplumber.page import Page

from .models import ExtractionResult, ResourceEstimate

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"measured\s*(?:&|and)\s*indicated|\bm\s*&\s*i\b", re.I), "Measured & Indicated"),
    (re.compile(r"\bmeasured\b", re.I), "Measured"),
    (re.compile(r"\bindicated\b", re.I), "Indicated"),
    (re.compile(r"\binferred\b", re.I), "Inferred"),
    (re.compile(r"\bprobable\b", re.I), "Probable"),
    (re.compile(r"\bproven\b", re.I), "Proven"),
    (re.compile(r"\btotal\b", re.I), "Total"),
]

_COMMODITY_SYMBOLS = (
    "TREO", "Li2O", "Ta2O5", "U3O8", "Graphite",
    "Cu", "Au", "Ag", "Zn", "Ni", "Fe", "Li", "Ta", "Mo", "Pb", "Sn", "Co", "Mn",
)
_COMMODITY_RE = re.compile(r"\b(" + "|".join(_COMMODITY_SYMBOLS) + r")\b")

_GRADE_UNIT_RE = re.compile(r"(g/t|gpt|ppm|%)", re.I)
_CONTAINED_UNIT_RE = re.compile(r"\b(Moz|koz|Mlb|kt|Mt|mlb|oz|lb|t)\b")
_TONNAGE_UNIT_RE = re.compile(r"\b(Mt|kt|million\s+tonnes?|million\s+tons?|tonnes?|tons?)\b", re.I)

_HEADER_TONNAGE_RE = re.compile(r"tonn|million\s+tonnes|quantity|\bore\b|\bmt\b|\bkt\b", re.I)
_HEADER_GRADE_RE = re.compile(r"grade|g/t|gpt|\bppm\b|%", re.I)
_HEADER_CONTAINED_RE = re.compile(r"contained|metal", re.I)
_HEADER_CATEGORY_RE = re.compile(r"categor|class|resource", re.I)

_NUMBER_RE = re.compile(r"-?\d[\d,\s]*(?:\.\d+)?")

_TEXT_ROW_RE = re.compile(
    r"(?P<cat>measured\s*(?:&|and)\s*indicated|\bm\s*&\s*i\b|measured|indicated|inferred)"
    r"[^.\n]{0,40}?"
    r"(?P<tonnage>\d[\d,]*(?:\.\d+)?)\s*(?P<tunit>Mt|kt|million\s+tonnes?)"
    r"\s*(?:@|at)\s*(?P<grade>\d[\d,]*(?:\.\d+)?)\s*(?P<gunit>g/t|gpt|ppm|%)\s*(?P<commodity>[A-Za-z][A-Za-z0-9]{0,5})?"
    r"(?:\s*(?:for|containing)\s*(?P<contained>\d[\d,]*(?:\.\d+)?)\s*(?P<cunit>Moz|koz|Mlb|kt|Mt|oz|lb|t))?",
    re.I,
)

_JUNK_NUMBERS = {"-", "--", "—", "–", "n/a", "na", "nil", ""}


# ---------------------------------------------------------------------------
# Small parsers
# ---------------------------------------------------------------------------


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.strip().lower()
    if cleaned in _JUNK_NUMBERS:
        return None
    match = _NUMBER_RE.search(cleaned)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "").replace(" ", ""))
    except ValueError:
        return None


def _parse_category(raw: str) -> str | None:
    for pattern, canonical in _CATEGORY_PATTERNS:
        if pattern.search(raw):
            return canonical
    return None


def _to_mt(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    unit_l = (unit or "Mt").strip().lower()
    if unit_l.startswith("kt"):
        return value / 1000.0
    return value


def _commodity_in(header: str) -> str | None:
    match = _COMMODITY_RE.search(header)
    return match.group(1) if match else None


def _grade_unit_in(header: str) -> str | None:
    match = _GRADE_UNIT_RE.search(header)
    if not match:
        return None
    unit = match.group(1)
    return "g/t" if unit.lower() == "gpt" else unit


def _contained_unit_in(header: str) -> str | None:
    match = _CONTAINED_UNIT_RE.search(header)
    if not match:
        return None
    unit = match.group(1)
    return {"mlb": "Mlb"}.get(unit.lower(), unit)


# ---------------------------------------------------------------------------
# Table mode
# ---------------------------------------------------------------------------


class _ColumnMap:
    """Column indices of a resource-statement table, parsed from its header."""

    def __init__(self) -> None:
        self.category: int | None = None
        self.tonnage: int | None = None
        self.tonnage_unit: str | None = None
        self.grades: dict[str, int] = {}  # commodity -> column
        self.grade_units: dict[str, str | None] = {}
        self.contained: dict[str, int] = {}  # commodity -> column
        self.contained_units: dict[str, str | None] = {}

    @property
    def usable(self) -> bool:
        has_tonnage = self.tonnage is not None or len(self.grades) > 0
        return has_tonnage and self.category is not None


def _build_column_map(rows: list[list[str]], header_index: int) -> _ColumnMap:
    """Map columns using the header row, joining up to two header rows if the
    grade/contained split lives on a second line (common in NI 43-101 tables)."""
    width = max(len(r) for r in rows)
    header_cells: list[str] = []
    for col in range(width):
        parts = []
        for row in rows[header_index : header_index + 2]:
            if col < len(row):
                parts.append(row[col].strip())
        header_cells.append(" ".join(p for p in parts if p))

    column_map = _ColumnMap()
    for index, header in enumerate(header_cells):
        if not header:
            continue
        commodity = _commodity_in(header)
        if _HEADER_CONTAINED_RE.search(header) and commodity:
            column_map.contained[commodity] = index
            column_map.contained_units[commodity] = _contained_unit_in(header)
            continue
        if _HEADER_GRADE_RE.search(header) and commodity:
            column_map.grades[commodity] = index
            column_map.grade_units[commodity] = _grade_unit_in(header)
            continue
        if _HEADER_TONNAGE_RE.search(header) and column_map.tonnage is None:
            column_map.tonnage = index
            unit_match = _TONNAGE_UNIT_RE.search(header)
            column_map.tonnage_unit = unit_match.group(1) if unit_match else None
            continue
        if _HEADER_CATEGORY_RE.search(header) and column_map.category is None:
            column_map.category = index
    return column_map


def _find_header_row(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows[:4]):
        joined = " ".join(row).lower()
        header_hits = sum(
            1
            for probe in ("tonn", "grade", "contained", "categor", "resource", "class", "%", "g/t")
            if probe in joined
        )
        if header_hits >= 2:
            return index
    return None


def _parse_table(table: list[list[str | None]], page_number: int) -> tuple[list[ResourceEstimate], list[str]]:
    rows = [[(cell or "").strip() for cell in row] for row in table]
    rows = [row for row in rows if any(row)]
    if len(rows) < 2:
        return [], []

    header_index = _find_header_row(rows)
    if header_index is None:
        return [], []

    column_map = _build_column_map(rows, header_index)
    if not column_map.usable:
        return [], []

    estimates: list[ResourceEstimate] = []
    warnings: list[str] = []
    for row in rows[header_index + 1 :]:
        raw_category = ""
        if column_map.category is not None and column_map.category < len(row):
            raw_category = row[column_map.category]
        category = _parse_category(raw_category) or _parse_category(" ".join(row))
        if not category:
            continue

        tonnage = None
        if column_map.tonnage is not None and column_map.tonnage < len(row):
            tonnage = _to_mt(_parse_number(row[column_map.tonnage]), column_map.tonnage_unit)

        emitted = False
        for commodity, grade_col in column_map.grades.items():
            grade = _parse_number(row[grade_col]) if grade_col < len(row) else None
            contained_col = column_map.contained.get(commodity)
            contained = (
                _parse_number(row[contained_col])
                if contained_col is not None and contained_col < len(row)
                else None
            )
            if tonnage is None and grade is None and contained is None:
                continue
            estimates.append(
                ResourceEstimate(
                    category=category,
                    commodity=commodity,
                    tonnage_mt=tonnage,
                    grade=grade,
                    grade_unit=column_map.grade_units.get(commodity),
                    contained_metal=contained,
                    contained_unit=column_map.contained_units.get(commodity),
                    page=page_number,
                    evidence=" | ".join(row),
                    confidence=1.0,
                )
            )
            emitted = True

        if not emitted and tonnage is not None:
            estimates.append(
                ResourceEstimate(
                    category=category,
                    commodity="unknown",
                    tonnage_mt=tonnage,
                    page=page_number,
                    evidence=" | ".join(row),
                    confidence=0.8,
                )
            )
            emitted = True

        if not emitted:
            warnings.append(
                f"page {page_number}: row mentions {category!r} but no tonnage/grade parsed: {' | '.join(row)}"
            )

    return estimates, warnings


# ---------------------------------------------------------------------------
# Text mode
# ---------------------------------------------------------------------------


def _parse_text_lines(text: str, page_number: int) -> list[ResourceEstimate]:
    estimates: list[ResourceEstimate] = []
    for line in text.splitlines():
        match = _TEXT_ROW_RE.search(line)
        if not match:
            continue
        category = _parse_category(match.group("cat"))
        if not category:
            continue
        commodity = (match.group("commodity") or "").upper() or "unknown"
        commodity = {
            "LI2O": "Li2O", "CU": "Cu", "AU": "Au", "AG": "Ag", "ZN": "Zn", "NI": "Ni", "FE": "Fe",
        }.get(commodity, commodity)
        grade_unit = match.group("gunit")
        if grade_unit.lower() == "gpt":
            grade_unit = "g/t"
        estimates.append(
            ResourceEstimate(
                category=category,
                commodity=commodity,
                tonnage_mt=_to_mt(_parse_number(match.group("tonnage")), match.group("tunit")),
                grade=_parse_number(match.group("grade")),
                grade_unit=grade_unit,
                contained_metal=_parse_number(match.group("contained")),
                contained_unit=match.group("cunit"),
                page=page_number,
                evidence=line.strip(),
                confidence=0.7,
            )
        )
    return estimates


# ---------------------------------------------------------------------------
# Metadata heuristics
# ---------------------------------------------------------------------------

_COMPANY_LINE_RE = re.compile(r"^\s*(?:company|issuer)\s*[:\-]\s*(.+?)\s*$", re.I | re.M)
_PROJECT_LINE_RE = re.compile(r"^\s*(?:project|property)\s*[:\-]\s*(.+?)\s*$", re.I | re.M)
_TITLE_LINE_RE = re.compile(r"^.*NI\s*43-101.*$", re.I | re.M)
_EFFECTIVE_DATE_RE = re.compile(r"effective\s+date\s*[:\-]?\s*([A-Z][a-z]+\s+\d{1,2},\s*\d{4})", re.I)


def _extract_metadata(first_pages_text: str) -> tuple[str | None, str | None, str | None, str | None]:
    title_match = _TITLE_LINE_RE.search(first_pages_text)
    report_title = title_match.group(0).strip() if title_match else None
    company_match = _COMPANY_LINE_RE.search(first_pages_text)
    project_match = _PROJECT_LINE_RE.search(first_pages_text)
    date_match = _EFFECTIVE_DATE_RE.search(first_pages_text)
    return (
        report_title,
        project_match.group(1).strip() if project_match else None,
        company_match.group(1).strip() if company_match else None,
        date_match.group(1) if date_match else None,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _dedupe(estimates: list[ResourceEstimate]) -> list[ResourceEstimate]:
    """Keep the highest-confidence row per (category, commodity, page)."""
    best: dict[tuple[str, str, int], ResourceEstimate] = {}
    for estimate in estimates:
        key = (estimate.category.lower(), estimate.commodity.lower(), estimate.page)
        current = best.get(key)
        if current is None or estimate.confidence > current.confidence:
            best[key] = estimate
    return list(best.values())


def extract_resources_from_pdf(pdf_path: str, source_uri: str | None = None) -> ExtractionResult:
    """Extract resource estimates from a local PDF file."""
    with open(pdf_path, "rb") as handle:
        payload = handle.read()
    sha256 = hashlib.sha256(payload).hexdigest()

    estimates: list[ResourceEstimate] = []
    warnings: list[str] = []
    first_pages_text: list[str] = []
    used_table = False
    used_text = False

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_text = ""
            try:
                page_text = _page_text(page)
            except Exception as exc:  # noqa: BLE001 - one bad page must not sink the doc
                warnings.append(f"page {page_index}: text extraction failed ({exc})")

            if page_index <= 3 and page_text:
                first_pages_text.append(page_text)

            try:
                tables = page.extract_tables()
            except Exception as exc:  # noqa: BLE001
                tables = []
                warnings.append(f"page {page_index}: table extraction failed ({exc})")

            for table in tables or []:
                table_rows, table_warnings = _parse_table(table, page_index)
                if table_rows:
                    used_table = True
                    estimates.extend(table_rows)
                warnings.extend(table_warnings)

            if page_text:
                text_rows = _parse_text_lines(page_text, page_index)
                if text_rows:
                    used_text = True
                    estimates.extend(text_rows)

        page_count = len(pdf.pages)

    merged = _dedupe(estimates)
    # Stable, human-friendly ordering: by page, then category, then commodity.
    merged.sort(key=lambda e: (e.page, e.category, e.commodity))

    meta_text = "\n".join(first_pages_text)
    report_title, project_name, company, effective_date = _extract_metadata(meta_text)

    if used_table and used_text:
        method = "table+text"
    elif used_table:
        method = "table"
    else:
        method = "text"

    return ExtractionResult(
        source=source_uri or pdf_path,
        resolved_path=str(pdf_path),
        sha256=sha256,
        page_count=page_count,
        report_title=report_title,
        project_name=project_name,
        company=company,
        effective_date=effective_date,
        estimates=merged,
        warnings=warnings,
        method=method,
        generated_at=datetime.now(timezone.utc),
    )


def _page_text(page: Page) -> str:
    return page.extract_text() or ""
