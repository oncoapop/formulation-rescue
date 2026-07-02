from datetime import date

from formulation_rescue.scoring import CandidateMetrics, score_candidate


def test_high_opportunity_synthetic_candidate():
    metrics = CandidateMetrics(
        ingredient_name="Synthetic A",
        product_count=1,
        active_product_count=0,
        discontinued_product_count=1,
        tentative_or_nonmarketed_count=0,
        unknown_marketing_status_count=0,
        all_products_discontinued=True,
        mixed_active_discontinued=False,
        sponsor_count=1,
        route_diversity_count=1,
        dosage_form_diversity_count=1,
        latest_patent_expiry="2020-01-01",
        latest_exclusivity_expiry=None,
        has_discontinued_product=True,
        has_iv_only_or_injectable_only=True,
        parenteral_route_signal=True,
        patent_count=1,
        exclusivity_count=0,
        unknown_route_count=0,
        unknown_dosage_form_count=0,
        source_conflict_flags="",
        mapping_quality_flags="exact_single_ingredient",
    )

    result = score_candidate(metrics, date(2026, 1, 1))

    assert result["score_ip_openness"] == 3
    assert result["score_route_gap"] == 2
    assert result["score_discontinued_or_fragile"] == 3
    assert result["score_reformulation_white_space"] == 2
    assert result["score_total"] == 10
    assert result["score_confidence"] == "high"
    assert "injectable-only" in result["phase1_notes"]


def test_future_ip_reduces_score():
    metrics = CandidateMetrics(
        ingredient_name="Synthetic B",
        product_count=3,
        active_product_count=3,
        discontinued_product_count=0,
        tentative_or_nonmarketed_count=0,
        unknown_marketing_status_count=0,
        all_products_discontinued=False,
        mixed_active_discontinued=False,
        sponsor_count=2,
        route_diversity_count=3,
        dosage_form_diversity_count=4,
        latest_patent_expiry="2030-01-01",
        latest_exclusivity_expiry="2029-01-01",
        has_discontinued_product=False,
        has_iv_only_or_injectable_only=False,
        parenteral_route_signal=False,
        patent_count=1,
        exclusivity_count=1,
        unknown_route_count=0,
        unknown_dosage_form_count=0,
        source_conflict_flags="",
        mapping_quality_flags="exact_single_ingredient",
    )

    result = score_candidate(metrics, date(2026, 1, 1))

    assert result["score_ip_openness"] == 0
    assert result["score_total"] == 0
