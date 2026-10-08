"""Structured output of NI 43-101 mineral-resource extraction.

One ``ResourceEstimate`` corresponds to one (category, commodity) pair on one
report page — the geometry of a NI 43-101 resource statement. ``evidence``
carries the raw table row / source line the numbers came from, so the brief
can cite it and a human reviewer can verify it without opening the PDF.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResourceEstimate(BaseModel):
    """A single resource row: category + commodity + tonnage + grade + metal."""

    category: str = Field(
        description="Measured / Indicated / Inferred / Measured & Indicated / Total"
    )
    commodity: str = Field(
        description="Element or oxide the grade and contained metal refer to, e.g. 'Li2O', 'Cu', 'Au'."
    )
    tonnage_mt: float | None = Field(
        default=None, description="Ore tonnage in millions of tonnes (Mt)."
    )
    grade: float | None = None
    grade_unit: str | None = Field(default=None, description="'%', 'g/t' or 'ppm'.")
    contained_metal: float | None = None
    contained_unit: str | None = Field(
        default=None, description="'oz', 'koz', 'Moz', 't', 'kt', 'Mt' or 'Mlb'."
    )
    page: int = Field(description="1-based PDF page number the row was found on.")
    evidence: str = Field(description="Raw source row / line the numbers were parsed from.")
    confidence: float = Field(description="1.0 = structured table row; 0.7 = text regex match.")


class ExtractionResult(BaseModel):
    """Everything ``extract_resources`` knows about one document."""

    source: str = Field(description="URI the caller passed in.")
    resolved_path: str = Field(description="Local filesystem path of the (possibly cached) PDF.")
    sha256: str
    page_count: int
    report_title: str | None = None
    project_name: str | None = None
    company: str | None = None
    effective_date: str | None = Field(
        default=None, description="Report effective date, if stated."
    )
    estimates: list[ResourceEstimate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    method: str = Field(
        description="'table', 'text' or 'table+text' depending on what produced results."
    )
    generated_at: datetime
