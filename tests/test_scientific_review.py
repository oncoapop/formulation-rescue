import csv

import pytest

from formulation_rescue.scientific_review import (
    REVIEW_COLUMNS,
    build_top100_scientific_review,
    interpret_scientific_signals,
)


@pytest.fixture
def base_row():
    return {
        "ingredient_name": "TEST DRUG",
        "triage_class": "therapeutic_drug",
        "triage_subclass": "small_molecule_or_other_therapeutic",
        "label_match_quality": "exact",
        "score_label_evidence_confidence": "3",
        "score_administration_burden": "2",
        "score_safety_burden": "1",
        "score_formulation_handling_burden": "2",
        "score_pediatric_gap": "0",
        "parenteral_route_signal": "1",
        "all_products_discontinued": "0",
        "mixed_active_discontinued": "1",
        "canonical_route_list": "intravenous",
        "formulation_burden_terms": "reconstitution",
        "administration_burden_terms": "infusion administration",
    }


def test_infusion_and_injection_site_classification(base_row):
    infusion = interpret_scientific_signals(base_row, "An infusion-related reaction was observed.")
    local = interpret_scientific_signals(base_row, "Injection-site reaction and injection site pain occurred.")
    assert infusion["toxicity_signal_class"] == "infusion_related"
    assert infusion["toxicity_formulation_sensitivity"] in {"likely", "possible"}
    assert local["toxicity_signal_class"] == "route_local"
    assert local["toxicity_formulation_sensitivity"] == "likely"


def test_intrinsic_and_exposure_classification(base_row):
    liver = interpret_scientific_signals(base_row, "Hepatotoxicity and severe liver injury may occur.")
    peak = interpret_scientific_signals(base_row, "Cmax and peak plasma concentration were associated with sedation after dosing.")
    assert liver["toxicity_signal_class"] == "organ_toxicity"
    assert liver["toxicity_formulation_sensitivity"] == "unlikely"
    assert liver["manual_safety_review_required"] == 1
    assert peak["toxicity_signal_class"] == "exposure_peak_possible"
    assert peak["toxicity_formulation_sensitivity"] == "possible"


def test_dosing_and_ambiguous_metabolite_pk(base_row):
    frequent = interpret_scientific_signals(base_row, "Take every 4 hours. Titrate to effect. Steady state occurs later.")
    ambiguous = interpret_scientific_signals(
        base_row, "The active metabolite has a terminal half-life; parent clearance was also measured."
    )
    assert "every 4 hours" in frequent["dosing_frequency_terms"]
    assert frequent["score_pk_dosing_burden"] >= 2
    assert ambiguous["pk_parent_metabolite_ambiguous"] == 1
    assert ambiguous["pk_review_required"] == 1


def test_specialist_flags_and_overlap(base_row):
    oncology = interpret_scientific_signals(base_row, "Cytotoxic chemotherapy causes severe marrow suppression.")
    nti = interpret_scientific_signals(base_row, "This narrow therapeutic index drug requires therapeutic drug monitoring.")
    overlap = interpret_scientific_signals(
        base_row, "Infusion-related reaction and injection site pain occur. Hepatotoxicity can cause liver failure."
    )
    assert "oncology_cytotoxic" in oncology["specialist_review_flags"]
    assert oncology["suggested_manual_disposition"] == "specialist_category"
    assert "narrow_therapeutic_index" in nti["specialist_review_flags"]
    assert overlap["has_conflicting_toxicity_signals"] == 1
    assert overlap["toxicity_formulation_sensitivity"] == "conflicting"
    assert overlap["manual_safety_review_required"] == 1
    assert overlap["formulation_rescue_optimism_penalty"] > 0
    assert overlap["suggested_manual_disposition"] != "advance"


def test_dynamic_hypothesis_and_conservative_pathway(base_row):
    result = interpret_scientific_signals(
        base_row, "Reconstitution is required. Injection site pain may occur."
    )
    assert "injection site pain" in result["candidate_hypothesis"]
    assert "intravenous" in result["candidate_hypothesis"]
    assert result["potential_regulatory_pathway"] == "possible_505b2_route_or_form_change"
    assert result["regulatory_pathway_confidence"] != "high"


def test_low_quality_evidence_avoids_false_precision(base_row):
    row = {**base_row, "label_match_quality": "low", "score_label_evidence_confidence": "1"}
    result = interpret_scientific_signals(row, "")
    assert result["toxicity_signal_class"] == "unknown"
    assert result["toxicity_formulation_sensitivity"] == "unknown"
    assert result["potential_regulatory_pathway"] == "unknown"
    assert result["suggested_manual_disposition"] == "deprioritise"


def test_offline_review_builder_preserves_fixed_rows(tmp_path):
    source = tmp_path / "signals.csv"
    output = tmp_path / "review.csv"
    report = tmp_path / "report.md"
    row = {
        column: ""
        for column in REVIEW_COLUMNS
        if column not in {"rank", *REVIEW_COLUMNS[26:]}
    }
    row.update(
        {
            "ingredient_name": "TEST DRUG",
            "triage_class": "therapeutic_drug",
            "triage_subclass": "small_molecule_or_other_therapeutic",
            "label_match_quality": "exact",
            "score_label_evidence_confidence": "3",
        }
    )
    input_columns = list(row)
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=input_columns)
        writer.writeheader()
        writer.writerow(row)
    reviewed = build_top100_scientific_review(source, output, report, tmp_path / "raw")
    assert len(reviewed) == 1
    with output.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames) == REVIEW_COLUMNS
    assert "hypothesis generation" in report.read_text(encoding="utf-8")
