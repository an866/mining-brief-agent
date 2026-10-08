"""Unit tests for NI 43-101 resource extraction against generated sample PDFs."""

from __future__ import annotations

from pathlib import Path

import pytest

from mineral_pdf_mcp.extract import extract_resources_from_pdf
from mineral_pdf_mcp.models import ResourceEstimate
from scripts.make_sample_pdf import build_all


@pytest.fixture(scope="module")
def samples(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    return build_all(tmp_path_factory.mktemp("samples"))


def _by_category(
    estimates: list[ResourceEstimate], category: str, commodity: str
) -> ResourceEstimate:
    for estimate in estimates:
        if estimate.category == category and estimate.commodity == commodity:
            return estimate
    found = [(e.category, e.commodity) for e in estimates]
    raise AssertionError(f"no estimate for {category}/{commodity}; got {found}")


class TestLithiumTable:
    def test_extracts_all_categories(self, samples: dict[str, Path]) -> None:
        result = extract_resources_from_pdf(str(samples["pilbara_lithium"]))
        categories = {e.category for e in result.estimates}
        assert {"Measured", "Indicated", "Measured & Indicated", "Inferred"} <= categories
        assert all(e.commodity == "Li2O" for e in result.estimates)

    def test_indicated_values(self, samples: dict[str, Path]) -> None:
        result = extract_resources_from_pdf(str(samples["pilbara_lithium"]))
        indicated = _by_category(result.estimates, "Indicated", "Li2O")
        assert indicated.tonnage_mt == pytest.approx(52.4)
        assert indicated.grade == pytest.approx(1.12)
        assert indicated.grade_unit == "%"
        assert indicated.contained_metal == pytest.approx(587)
        assert indicated.contained_unit == "kt"
        assert indicated.page == 2
        assert "Indicated" in indicated.evidence
        assert indicated.confidence == 1.0

    def test_inferred_values(self, samples: dict[str, Path]) -> None:
        result = extract_resources_from_pdf(str(samples["pilbara_lithium"]))
        inferred = _by_category(result.estimates, "Inferred", "Li2O")
        assert inferred.tonnage_mt == pytest.approx(34.8)
        assert inferred.grade == pytest.approx(0.94)
        assert inferred.contained_metal == pytest.approx(327)

    def test_metadata(self, samples: dict[str, Path]) -> None:
        result = extract_resources_from_pdf(str(samples["pilbara_lithium"]))
        assert result.project_name == "Pilbara Lithium Project (Demo)"
        assert result.company == "Demo Lithium Pty Ltd"
        assert result.effective_date == "March 31, 2025"
        assert result.report_title and "NI 43-101" in result.report_title
        assert result.method in ("table", "table+text")
        assert result.page_count >= 2


class TestCopperGoldTable:
    def test_emits_one_row_per_commodity(self, samples: dict[str, Path]) -> None:
        result = extract_resources_from_pdf(str(samples["andes_copper_gold"]))
        indicated_cu = _by_category(result.estimates, "Indicated", "Cu")
        indicated_au = _by_category(result.estimates, "Indicated", "Au")
        assert indicated_cu.tonnage_mt == pytest.approx(120.5)
        assert indicated_au.tonnage_mt == pytest.approx(120.5)
        assert indicated_cu.grade == pytest.approx(0.62)
        assert indicated_cu.grade_unit == "%"
        assert indicated_au.grade == pytest.approx(0.31)
        assert indicated_au.grade_unit == "g/t"
        assert indicated_cu.contained_metal == pytest.approx(747)
        assert indicated_cu.contained_unit == "kt"
        assert indicated_au.contained_metal == pytest.approx(1201)
        assert indicated_au.contained_unit == "koz"

    def test_inferred_row(self, samples: dict[str, Path]) -> None:
        result = extract_resources_from_pdf(str(samples["andes_copper_gold"]))
        inferred = _by_category(result.estimates, "Inferred", "Cu")
        assert inferred.tonnage_mt == pytest.approx(48.3)
        assert inferred.contained_metal == pytest.approx(213)


class TestProseStatement:
    def test_text_mode_extraction(self, samples: dict[str, Path]) -> None:
        result = extract_resources_from_pdf(str(samples["prose_resources"]))
        assert result.method == "text"
        indicated_cu = _by_category(result.estimates, "Indicated", "Cu")
        assert indicated_cu.tonnage_mt == pytest.approx(52.4)
        assert indicated_cu.grade == pytest.approx(1.02)
        assert indicated_cu.contained_metal == pytest.approx(534)
        assert indicated_cu.contained_unit == "kt"
        assert indicated_cu.confidence == 0.7
        inferred_au = _by_category(result.estimates, "Inferred", "Au")
        assert inferred_au.tonnage_mt == pytest.approx(21.7)
        assert inferred_au.grade == pytest.approx(0.88)
        assert inferred_au.contained_metal == pytest.approx(614)
        assert inferred_au.contained_unit == "koz"

    def test_no_duplicate_rows(self, samples: dict[str, Path]) -> None:
        result = extract_resources_from_pdf(str(samples["prose_resources"]))
        keys = [(e.category, e.commodity) for e in result.estimates]
        assert len(keys) == len(set(keys))
