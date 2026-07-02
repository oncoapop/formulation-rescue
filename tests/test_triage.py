import pytest

from formulation_rescue.triage import classify_candidate


@pytest.mark.parametrize(
    ("ingredient", "application_types", "expected_class", "excluded"),
    [
        ("CALCIUM", "NDA", "electrolyte_mineral_nutrient", True),
        ("CALCIUM METRIZOATE", "NDA", "contrast_agent", True),
        (
            "ALBUMIN IODINATED I-131 SERUM",
            "NDA",
            "radiopharmaceutical",
            True,
        ),
        ("ALBIGLUTIDE", "BLA", "biologic_or_peptide", False),
        ("BREXANOLONE", "NDA", "therapeutic_drug", False),
        ("CEFMETAZOLE SODIUM", "NDA", "obsolete_antibiotic", False),
    ],
)
def test_required_triage_examples(
    ingredient, application_types, expected_class, excluded
):
    result = classify_candidate(
        {
            "ingredient_name": ingredient,
            "application_type_list": application_types,
            "canonical_route_list": "intravenous",
            "canonical_dosage_form_list": "solution",
        },
        score_total=8,
    )

    assert result.triage_class == expected_class
    assert result.exclude_from_top_science_review is excluded
    assert result.science_review_priority == (
        "excluded"
        if excluded
        else "medium"
        if expected_class == "obsolete_antibiotic"
        else "high"
    )
