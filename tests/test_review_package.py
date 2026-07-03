import csv
import zipfile
from datetime import date

import pytest

from formulation_rescue.review_package import (
    INDEX_COLUMNS,
    build_review_package,
)
from formulation_rescue.scientific_review import REVIEW_COLUMNS


def test_build_review_package(tmp_path):
    source = tmp_path / "review.csv"
    rows = []
    for rank in range(1, 101):
        row = {column: "" for column in REVIEW_COLUMNS}
        row.update(
            {
                "rank": str(rank),
                "ingredient_name": f"DRUG {rank}",
                "triage_class": "therapeutic_drug",
                "triage_subclass": "small_molecule_or_other_therapeutic",
                "scientific_rescue_signal_score": "12",
                "toxicity_signal_class": "route_local",
                "toxicity_formulation_sensitivity": "possible",
                "dominant_toxicity_concern": "injection site pain",
                "administration_burden_terms": "injection administration",
                "safety_burden_terms": "injection site pain",
                "formulation_burden_terms": "reconstitution",
                "potential_regulatory_pathway": "possible_505b2_route_or_form_change",
                "suggested_manual_disposition": "literature_review",
                "candidate_hypothesis": f"DRUG {rank} has injection site pain requiring row-specific review.",
                "next_evidence_needed": "PK/PD review",
                "label_match_quality": "exact",
            }
        )
        rows.append(row)
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    result = build_review_package(source, tmp_path / "exports", date(2026, 7, 2))
    package = result["package_path"]
    assert result["candidate_packets"] == 100
    assert (package / "README.md").exists()
    assert (package / "MANIFEST.md").exists()
    assert (package / "top100_scientific_review.xlsx").exists()
    assert result["zip_path"].exists()
    with (package / "candidate_index.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames) == INDEX_COLUMNS
        assert len(list(reader)) == 100
    packet = package / "candidate_packets" / "001_DRUG_1.md"
    assert "injection site pain" in packet.read_text(encoding="utf-8")
    with zipfile.ZipFile(package / "top100_scientific_review.xlsx") as workbook:
        assert "xl/worksheets/sheet4.xml" in workbook.namelist()
        assert "Top100 Review" in workbook.read("xl/workbook.xml").decode()
    with zipfile.ZipFile(result["zip_path"]) as archive:
        assert any(name.endswith("/README.md") for name in archive.namelist())


def test_package_requires_exactly_100_rows(tmp_path):
    source = tmp_path / "review.csv"
    source.write_text("rank,ingredient_name\n1,ONE\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected fixed top-100"):
        build_review_package(source, tmp_path / "exports", date(2026, 7, 2))
