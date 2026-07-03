import csv

import pytest

from formulation_rescue.rescueability import (
    RESCUEABILITY_COLUMNS,
    VALID_QUEUES,
    active_ingredient_family,
    assign_review_queue,
    assign_tier,
    build_rescueability_review,
    classify_identity,
    normalize_ingredient_name,
    preliminary_rescueability_score,
    select_family_representatives,
)
from formulation_rescue.scientific_review import REVIEW_COLUMNS


def row_for(name, **updates):
    row = {column: "" for column in REVIEW_COLUMNS}
    row.update(
        {
            "rank": "1",
            "ingredient_name": name,
            "triage_class": "therapeutic_drug",
            "triage_subclass": "small_molecule_or_other_therapeutic",
            "scientific_rescue_signal_score": "24",
            "score_administration_burden": "3",
            "score_formulation_handling_burden": "3",
            "score_route_conversion_opportunity": "3",
            "score_label_evidence_confidence": "3",
            "label_match_quality": "exact",
            "toxicity_formulation_sensitivity": "possible",
            "canonical_route_list": "intravenous",
            "canonical_dosage_form_list": "powder",
            "formulation_burden_terms": "reconstitution; refrigeration",
        }
    )
    row.update(updates)
    row.update(classify_identity(row))
    return row


@pytest.mark.parametrize(
    "name",
    [
        "PACLITAXEL", "DOXORUBICIN", "CISPLATIN", "CYTARABINE",
        "MELPHALAN", "TOPOTECAN", "IXABEPILONE",
    ],
)
def test_true_cytotoxic_classification(name):
    assert classify_identity(row_for(name))["true_cytotoxic_antineoplastic_flag"] == 1


@pytest.mark.parametrize(
    ("name", "base"),
    [
        ("DOXORUBICIN HYDROCHLORIDE", "DOXORUBICIN"),
        ("BENDAMUSTINE HYDROCHLORIDE", "BENDAMUSTINE"),
        ("MELPHALAN HYDROCHLORIDE", "MELPHALAN"),
    ],
)
def test_salt_base_name_matching(name, base):
    assert normalize_ingredient_name(name) == base
    assert classify_identity(row_for(name))["true_cytotoxic_antineoplastic_flag"] == 1


@pytest.mark.parametrize(
    "name",
    ["ABATACEPT", "BELATACEPT", "INFLIXIMAB", "TOCILIZUMAB", "ETANERCEPT", "VEDOLIZUMAB"],
)
def test_immunomodulator_not_misclassified_as_true_cytotoxic(name):
    result = classify_identity(
        row_for(
            name,
            triage_class="biologic_or_peptide",
            toxicity_signal_class="oncology_cytotoxic",
            safety_burden_terms="cytotoxic; malignancy; neutropenia; infection",
        )
    )
    assert result["true_cytotoxic_antineoplastic_flag"] == 0
    assert result["immunomodulator_warning_flag"] == 1
    assert result["cytotoxic_context_only_flag"] == 1


@pytest.mark.parametrize(
    "name",
    [
        "FAM-TRASTUZUMAB DERUXTECAN-NXKI", "BLINATUMOMAB", "RITUXIMAB",
        "CETUXIMAB", "PANITUMUMAB", "OBINUTUZUMAB",
    ],
)
def test_oncology_biologic_or_adc(name):
    assert classify_identity(row_for(name))["oncology_biologic_or_adc_flag"] == 1


@pytest.mark.parametrize(
    ("family", "members", "representative"),
    [
        ("RITUXIMAB", ["RITUXIMAB-ABBS", "RITUXIMAB", "RITUXIMAB-PVVR", "RITUXIMAB-ARRX"], "RITUXIMAB"),
        ("TRASTUZUMAB", ["TRASTUZUMAB-QYYP", "TRASTUZUMAB", "TRASTUZUMAB-DKST", "TRASTUZUMAB-STRF"], "TRASTUZUMAB"),
        ("INFLIXIMAB", ["INFLIXIMAB-DYYB", "INFLIXIMAB", "INFLIXIMAB-AXXQ"], "INFLIXIMAB"),
        ("TOCILIZUMAB", ["TOCILIZUMAB-AAZG", "TOCILIZUMAB"], "TOCILIZUMAB"),
        ("ECULIZUMAB", ["ECULIZUMAB-AEEB", "ECULIZUMAB"], "ECULIZUMAB"),
    ],
)
def test_unsuffixed_family_representative(family, members, representative):
    rows = []
    for name in members:
        row = row_for(name)
        row["active_ingredient_family"] = active_ingredient_family(name)
        row["rescueability_score"] = 99 if name != representative else 1
        rows.append(row)
    assert select_family_representatives(rows)[family][0] == representative


def test_deterministic_representative_fallback_order():
    rows = []
    values = [
        ("RITUXIMAB-PVVR", 10, 1, 1, 20),
        ("RITUXIMAB-ABBS", 11, 0, 0, 1),
        ("RITUXIMAB-ARRX", 10, 3, 3, 30),
    ]
    for name, score, formulation, administration, scientific in values:
        row = row_for(name)
        row.update(
            {
                "active_ingredient_family": "RITUXIMAB",
                "rescueability_score": score,
                "score_formulation_handling_burden": formulation,
                "score_administration_burden": administration,
                "scientific_rescue_signal_score": scientific,
            }
        )
        rows.append(row)
    assert select_family_representatives(rows)["RITUXIMAB"][0] == "RITUXIMAB-ABBS"
    rows[0]["rescueability_score"] = 11
    rows[2]["rescueability_score"] = 11
    assert select_family_representatives(rows)["RITUXIMAB"][0] == "RITUXIMAB-ARRX"
    rows[0]["score_formulation_handling_burden"] = 3
    rows[0]["score_administration_burden"] = 4
    assert select_family_representatives(rows)["RITUXIMAB"][0] == "RITUXIMAB-PVVR"
    rows[2]["score_administration_burden"] = 4
    rows[2]["scientific_rescue_signal_score"] = 31
    assert select_family_representatives(rows)["RITUXIMAB"][0] == "RITUXIMAB-ARRX"
    for row in rows:
        row.update(
            {
                "score_formulation_handling_burden": 3,
                "score_administration_burden": 4,
                "scientific_rescue_signal_score": 31,
            }
        )
    assert select_family_representatives(rows)["RITUXIMAB"][0] == "RITUXIMAB-ABBS"


@pytest.mark.parametrize(
    "concern",
    [
        "renal failure", "hepatotoxicity", "anaphylaxis", "cytotoxic",
        "chemotherapy", "antineoplastic", "neutropenia", "myelosuppression",
    ],
)
def test_conflicting_severe_toxicity_never_a(concern):
    row = row_for(
        "TEST DRUG",
        toxicity_formulation_sensitivity="conflicting",
        dominant_toxicity_concern=concern,
    )
    row.update(
        {
            "rescueability_score": 99,
            "review_queue": "small_molecule_reformulation",
            "biosimilar_or_branded_family_duplicate_flag": 0,
            "duplicate_independent_review_reason": "",
        }
    )
    assert assign_tier(row) != "A_strong_near_term_review"


def test_clear_local_burden_can_be_high_tier_and_score_is_distinct():
    row = row_for("TEST DRUG", scientific_rescue_signal_score="24")
    score = preliminary_rescueability_score(row)
    row.update(
        {
            "rescueability_score": score,
            "review_queue": "small_molecule_reformulation",
            "biosimilar_or_branded_family_duplicate_flag": 0,
            "duplicate_independent_review_reason": "",
        }
    )
    assert score != 24
    assert assign_tier(row) in {
        "A_strong_near_term_review", "B_plausible_literature_review"
    }


def test_true_cytotoxic_is_specialist_tier():
    row = row_for("PACLITAXEL")
    row.update(
        {
            "rescueability_score": 30,
            "review_queue": assign_review_queue(row),
            "biosimilar_or_branded_family_duplicate_flag": 0,
            "duplicate_independent_review_reason": "",
        }
    )
    assert row["review_queue"] == "oncology_specialist"
    assert assign_tier(row) == "C_specialist_only_review"


def test_independently_reviewable_duplicate_is_not_automatically_buried():
    row = row_for("TEST DRUG-ABBS")
    row.update(
        {
            "rescueability_score": 14,
            "review_queue": "small_molecule_reformulation",
            "biosimilar_or_branded_family_duplicate_flag": 1,
            "duplicate_independent_review_reason": "distinct subcutaneous route",
        }
    )
    assert assign_tier(row) == "B_plausible_literature_review"


def test_context_only_can_be_false_positive():
    row = row_for(
        "UNRELATED DRUG",
        toxicity_signal_class="oncology_cytotoxic",
        score_administration_burden="0",
        score_formulation_handling_burden="0",
        score_route_conversion_opportunity="0",
    )
    row.update(classify_identity(row))
    row.update(
        {
            "rescueability_score": preliminary_rescueability_score(row),
            "biosimilar_or_branded_family_duplicate_flag": 0,
            "duplicate_independent_review_reason": "",
        }
    )
    row["review_queue"] = assign_review_queue(row)
    assert row["review_queue"] == "deprioritise_or_false_positive"
    assert assign_tier(row) == "E_likely_false_positive"


def test_full_output_preserves_duplicates_assigns_queues_and_reports(tmp_path):
    source = tmp_path / "review.csv"
    output = tmp_path / "rescue.csv"
    report = tmp_path / "report.md"
    queues = tmp_path / "queues.md"
    rows = []
    names = ["RITUXIMAB", "RITUXIMAB-ABBS"] + [f"TEST DRUG {index}" for index in range(3, 101)]
    for rank, name in enumerate(names, start=1):
        row = row_for(name)
        row["rank"] = str(rank)
        if name.startswith("RITUXIMAB"):
            row["triage_class"] = "biologic_or_peptide"
        rows.append(row)
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=REVIEW_COLUMNS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    reviewed = build_rescueability_review(source, output, report, queues)
    assert len(reviewed) == 100
    assert all(row["review_queue"] in VALID_QUEUES for row in reviewed)
    assert sum(row["active_ingredient_family"] == "RITUXIMAB" for row in reviewed) == 2
    duplicate = next(row for row in reviewed if row["ingredient_name"] == "RITUXIMAB-ABBS")
    assert duplicate["biosimilar_or_branded_family_duplicate_flag"] == 1
    assert duplicate["family_representative_ingredient"] == "RITUXIMAB"
    assert duplicate["duplicate_independent_review_reason"] == ""
    assert duplicate["rescueability_tier"] == "D_deprioritise"
    with output.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert set(RESCUEABILITY_COLUMNS).issubset(reader.fieldnames)
        assert len(list(reader)) == 100
    main_text = report.read_text(encoding="utf-8")
    queue_text = queues.read_text(encoding="utf-8")
    assert "Counts by review queue" in main_text
    assert "Counts by rescueability tier" in main_text
    assert "Duplicate family clusters and representatives" in main_text
    assert "Likely false positives" in main_text
    assert len(main_text) > 3000
    assert "Recommended next action" in queue_text
    assert len(queue_text) > 2000
