"""Transparent Phase 1 screening heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CandidateMetrics:
    ingredient_name: str
    product_count: int
    sponsor_count: int
    route_diversity_count: int
    dosage_form_diversity_count: int
    latest_patent_expiry: str | None
    latest_exclusivity_expiry: str | None
    has_discontinued_product: bool
    has_iv_only_or_injectable_only: bool


def _is_future(iso_date: str | None, as_of: date) -> bool:
    return bool(iso_date and date.fromisoformat(iso_date) > as_of)


def score_ip_openness(
    latest_patent_expiry: str | None,
    latest_exclusivity_expiry: str | None,
    as_of: date,
) -> int:
    future_patent = _is_future(latest_patent_expiry, as_of)
    future_exclusivity = _is_future(latest_exclusivity_expiry, as_of)
    if future_patent and future_exclusivity:
        return 0
    if future_patent or future_exclusivity:
        return 1
    if latest_patent_expiry or latest_exclusivity_expiry:
        return 2
    return 3


def score_route_gap(route_count: int, injectable_only: bool) -> int:
    if injectable_only:
        return 3
    if route_count <= 1:
        return 2
    if route_count == 2:
        return 1
    return 0


def score_discontinued_or_fragile(discontinued: bool, sponsor_count: int) -> int:
    if discontinued and sponsor_count <= 1:
        return 3
    if discontinued:
        return 2
    if sponsor_count <= 1:
        return 1
    return 0


def score_reformulation_white_space(route_count: int, dosage_form_count: int) -> int:
    diversity = route_count + dosage_form_count
    if diversity <= 2:
        return 3
    if diversity <= 4:
        return 2
    if diversity <= 6:
        return 1
    return 0


def score_candidate(metrics: CandidateMetrics, as_of: date) -> dict[str, int | str]:
    components = {
        "score_ip_openness": score_ip_openness(
            metrics.latest_patent_expiry, metrics.latest_exclusivity_expiry, as_of
        ),
        "score_route_gap": score_route_gap(
            metrics.route_diversity_count, metrics.has_iv_only_or_injectable_only
        ),
        "score_discontinued_or_fragile": score_discontinued_or_fragile(
            metrics.has_discontinued_product, metrics.sponsor_count
        ),
        "score_reformulation_white_space": score_reformulation_white_space(
            metrics.route_diversity_count, metrics.dosage_form_diversity_count
        ),
    }
    notes = [
        label
        for enabled, label in (
            (metrics.has_iv_only_or_injectable_only, "injectable-only"),
            (metrics.has_discontinued_product, "discontinued product recorded"),
            (components["score_ip_openness"] >= 2, "limited future IP signal"),
            (components["score_reformulation_white_space"] >= 2, "low formulation diversity"),
        )
        if enabled
    ]
    return {
        **components,
        "score_total": sum(components.values()),
        "phase1_notes": "; ".join(notes) or "no priority flag",
    }
