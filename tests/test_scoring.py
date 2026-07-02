from datetime import date

from formulation_rescue.scoring import CandidateMetrics, score_candidate


def test_high_opportunity_synthetic_candidate():
    metrics = CandidateMetrics(
        ingredient_name="Synthetic A",
        product_count=1,
        sponsor_count=1,
        route_diversity_count=1,
        dosage_form_diversity_count=1,
        latest_patent_expiry="2020-01-01",
        latest_exclusivity_expiry=None,
        has_discontinued_product=True,
        has_iv_only_or_injectable_only=True,
    )

    result = score_candidate(metrics, date(2026, 1, 1))

    assert result["score_ip_openness"] == 2
    assert result["score_route_gap"] == 3
    assert result["score_discontinued_or_fragile"] == 3
    assert result["score_reformulation_white_space"] == 3
    assert result["score_total"] == 11
    assert "injectable-only" in result["phase1_notes"]


def test_future_ip_reduces_score():
    metrics = CandidateMetrics(
        ingredient_name="Synthetic B",
        product_count=3,
        sponsor_count=2,
        route_diversity_count=3,
        dosage_form_diversity_count=4,
        latest_patent_expiry="2030-01-01",
        latest_exclusivity_expiry="2029-01-01",
        has_discontinued_product=False,
        has_iv_only_or_injectable_only=False,
    )

    result = score_candidate(metrics, date(2026, 1, 1))

    assert result["score_ip_openness"] == 0
    assert result["score_total"] == 0
