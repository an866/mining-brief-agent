"""Generate the synthetic NI 43-101 style demo PDFs bundled in ``data/samples``.

These documents exist so the PDF extractor and the end-to-end brief have a
deterministic, license-clean corpus: three short reports covering (1) a
lithium table with Li2O grades, (2) a copper-gold table with per-commodity
grade/contained columns, and (3) a prose-only resource statement that
exercises the text-regex path. Every page carries a footer marking it as a
synthetic demo document.

Run ``python scripts/make_sample_pdf.py`` to (re)generate the files; the
``reportlab`` invariant flag pins embedded timestamps so output bytes are
reproducible.
"""

from __future__ import annotations

from pathlib import Path

from reportlab import rl_config

rl_config.invariant = 1  # reproducible PDF bytes (fixed timestamps/ids)

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Paragraph,
    PageBreak,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from mining_brief_core.paths import samples_dir  # noqa: E402

FOOTER_TEXT = (
    "DEMO document for mining-brief-agent - synthetic sample, not a real NI 43-101 report."
)

_PAGE_WIDTH, _PAGE_HEIGHT = A4
_MARGIN = 20 * mm


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontSize=16, leading=20, spaceAfter=6
        ),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], spaceBefore=10, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=10, leading=14),
        "note": ParagraphStyle("note", parent=base["BodyText"], fontSize=8, leading=11, textColor=colors.grey),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=9, leading=11),
    }


def _footer(canvas, doc) -> None:  # noqa: ANN001 - reportlab callback signature
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawString(_MARGIN, 12 * mm, FOOTER_TEXT)
    canvas.drawRightString(_PAGE_WIDTH - _MARGIN, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _build(dest: Path, filename: str, flowables: list) -> Path:  # noqa: ANN001
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / filename
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=20 * mm,
        title=filename,
        author="mining-brief-agent sample generator",
    )
    doc.build(flowables, onFirstPage=_footer, onLaterPages=_footer)
    return target


def _resource_table(header: list[str], rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(cell, styles["cell"]) for cell in header]]
    data += [[Paragraph(cell, styles["cell"]) for cell in row] for row in rows]
    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_pilbara_lithium(dest: Path) -> Path:
    styles = _styles()
    flow: list = [
        Paragraph(
            "NI 43-101 Technical Report on the Pilbara Lithium Project (Demo Sample)", styles["title"]
        ),
        Spacer(1, 4 * mm),
        Paragraph("Project: Pilbara Lithium Project (Demo)", styles["body"]),
        Paragraph("Company: Demo Lithium Pty Ltd", styles["body"]),
        Paragraph("Effective Date: March 31, 2025", styles["body"]),
        Paragraph("Report Date: May 15, 2025", styles["body"]),
        Paragraph("1  Summary", styles["h2"]),
        Paragraph(
            "This technical report has been prepared in accordance with National Instrument "
            "43-101 Standards of Disclosure for Mineral Projects. The Mineral Resource estimate "
            "for the Pilbara Lithium Project (Demo) is reported within a conceptual pit shell at "
            "a cut-off grade of 0.5% Li2O. Mineralisation is hosted in stacked pegmatite bodies "
            "with a strike length of approximately 3.2 kilometres.",
            styles["body"],
        ),
        PageBreak(),
        Paragraph("2  Mineral Resource Statement", styles["h2"]),
        Paragraph(
            "The Mineral Resource estimate for the Pilbara Lithium Project (Demo) is summarised "
            "in Table 2.1. Mineral Resources are reported at a cut-off grade of 0.5% Li2O using "
            "a lithium oxide (Li2O) grade basis.",
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        Paragraph("Table 2.1 - Mineral Resource Statement (Demo)", styles["body"]),
        Spacer(1, 2 * mm),
        _resource_table(
            ["Category", "Tonnes (Mt)", "Li2O Grade (%)", "Contained Li2O (kt)"],
            [
                ["Measured", "18.2", "1.31", "238"],
                ["Indicated", "52.4", "1.12", "587"],
                ["Measured & Indicated", "70.6", "1.17", "825"],
                ["Inferred", "34.8", "0.94", "327"],
            ],
            styles,
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            "Notes: (1) Mineral Resources are not Mineral Reserves and do not have demonstrated "
            "economic viability. (2) Tonnes are metric; Mt = million tonnes; kt = thousand tonnes. "
            "(3) Totals may not sum exactly due to rounding.",
            styles["note"],
        ),
    ]
    return _build(dest, "pilbara_li2o_ni43101_sample.pdf", flow)


def build_andes_copper_gold(dest: Path) -> Path:
    styles = _styles()
    flow: list = [
        Paragraph(
            "NI 43-101 Technical Report on the Andes Copper-Gold Project (Demo Sample)",
            styles["title"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("Project: Andes Copper-Gold Project (Demo)", styles["body"]),
        Paragraph("Company: Demo Andes Copper Pty Ltd", styles["body"]),
        Paragraph("Effective Date: January 31, 2025", styles["body"]),
        Paragraph("1  Summary", styles["h2"]),
        Paragraph(
            "This report presents the Mineral Resource estimate for the Andes Copper-Gold "
            "Project (Demo), a porphyry deposit reported at a cut-off grade of 0.30% Cu within "
            "a conceptual pit shell.",
            styles["body"],
        ),
        PageBreak(),
        Paragraph("2  Mineral Resource Statement", styles["h2"]),
        Paragraph(
            "The estimate is summarised in Table 2.1. Copper grade is reported as % Cu and gold "
            "grade as g/t Au; contained metal is reported in kt Cu and koz Au.",
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        _resource_table(
            [
                "Category",
                "Tonnes (Mt)",
                "Cu Grade (%)",
                "Au Grade (g/t)",
                "Contained Cu (kt)",
                "Contained Au (koz)",
            ],
            [
                ["Indicated", "120.5", "0.62", "0.31", "747", "1201"],
                ["Inferred", "48.3", "0.44", "0.24", "213", "373"],
                ["Total", "168.8", "0.57", "0.30", "960", "1574"],
            ],
            styles,
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            "Notes: (1) Mineral Resources are not Mineral Reserves. (2) Cut-off grade: 0.30% Cu. "
            "(3) koz = thousand troy ounces.",
            styles["note"],
        ),
    ]
    return _build(dest, "andes_cu_au_ni43101_sample.pdf", flow)


def build_prose_resources(dest: Path) -> Path:
    styles = _styles()
    flow: list = [
        Paragraph(
            "NI 43-101 Technical Report - Prose Resource Statement (Demo Sample)", styles["title"]
        ),
        Spacer(1, 4 * mm),
        Paragraph("Project: Prose Metals Deposit (Demo)", styles["body"]),
        Paragraph("Company: Demo Prose Metals Ltd", styles["body"]),
        Paragraph("Effective Date: February 28, 2025", styles["body"]),
        Paragraph("1  Summary", styles["h2"]),
        Paragraph(
            "This short demo report states its Mineral Resource estimate in running prose "
            "rather than in a table, to exercise text-based extraction.",
            styles["body"],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "Indicated Resources of 52.4 Mt at 1.02 % Cu for 534 kt Cu are reported at a "
            "0.3% Cu cut-off.",
            styles["body"],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "Inferred Resources of 21.7 Mt at 0.88 g/t Au for 614 koz Au are reported at a "
            "0.5 g/t Au cut-off.",
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            "Notes: Mineral Resources are not Mineral Reserves and do not have demonstrated "
            "economic viability.",
            styles["note"],
        ),
    ]
    return _build(dest, "prose_resources_note_sample.pdf", flow)


def build_all(dest: Path) -> dict[str, Path]:
    """Generate all sample PDFs into ``dest`` and return {name: path}."""
    return {
        "pilbara_lithium": build_pilbara_lithium(dest),
        "andes_copper_gold": build_andes_copper_gold(dest),
        "prose_resources": build_prose_resources(dest),
    }


def main() -> None:
    built = build_all(samples_dir())
    for name, path in built.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
