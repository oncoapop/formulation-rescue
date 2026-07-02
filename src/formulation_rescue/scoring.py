"""Transparent Phase 1 screening heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CandidateMetrics:
    ingredient_name: str
    product_count: int
    active_product_count: int
    discontinued_product_count: int
    tentative_or_nonmarketed_count: int
    unknown_marketing_status_count: int
    all_products_discontinued: bool
    mixed_active_discontinued: bool
    sponsor_count: int
    route_diversity_count: int
    dosage_form_diversity_count: int
    latest_patent_expiry: str | None
    latest_exclusivity_expiry: str | None
    has_discontinued_product: bool
    has_iv_only_or_injectable_only: bool
    parenteral_route_signal: bool
    patent_count: int
    exclusivity_count: int
    unknown_route_count: int
    unknown_dosage_form_count: int
    source_conflict_flags: str
    mapping_quality_flags: str


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
        return 3
    return 1


def score_route_gap(
    route_count: int, injectable_only: bool, parenteral_signal: bool = False
) -> int:
    if injectable_only:
        return 2
    if parenteral_signal and route_count <= 2:
        return 1
    if route_count <= 1:
        return 1
    return 0


def score_discontinued_or_fragile(
    all_discontinued: bool,
    mixed_active_discontinued: bool,
    active_product_count: int,
    sponsor_count: int,
) -> int:
    if all_discontinued and sponsor_count <= 1:
        return 3
    if all_discontinued:
        return 2
    if mixed_active_discontinued:
        return 1
    if active_product_count > 0 and sponsor_count <= 1:
        return 1
    return 0


def score_reformulation_white_space(route_count: int, dosage_form_count: int) -> int:
    # Route opportunity is scored separately; use dosage-form diversity here.
    if dosage_form_count <= 1:
        return 2
    if dosage_form_count == 2:
        return 1
    return 0


def data_completeness(metrics: CandidateMetrics) -> tuple[int, str, str]:
    checks = {
        "marketing status": metrics.unknown_marketing_status_count == 0,
        "route": metrics.unknown_route_count == 0,
        "dosage form": metrics.unknown_dosage_form_count == 0,
        "sponsor": metrics.sponsor_count > 0,
        "application type": "missing_application_type"
        not in metrics.source_conflict_flags,
        "ingredient-strength mapping": not any(
            flag in metrics.mapping_quality_flags
            for flag in ("ambiguous_multi_ingredient_strength", "unknown")
        ),
    }
    score = round(100 * sum(checks.values()) / len(checks))
    missing = [label for label, complete in checks.items() if not complete]
    notes = (
        "complete core evidence"
        if not missing
        else "incomplete: " + ", ".join(missing)
    )
    confidence = "high" if score >= 85 else "medium" if score >= 65 else "low"
    return score, confidence, notes


def score_candidate(metrics: CandidateMetrics, as_of: date) -> dict[str, int | str]:
    components = {
        "score_ip_openness": score_ip_openness(
            metrics.latest_patent_expiry, metrics.latest_exclusivity_expiry, as_of
        ),
        "score_route_gap": score_route_gap(
            metrics.route_diversity_count,
            metrics.has_iv_only_or_injectable_only,
            metrics.parenteral_route_signal,
        ),
        "score_discontinued_or_fragile": score_discontinued_or_fragile(
            metrics.all_products_discontinued,
            metrics.mixed_active_discontinued,
            metrics.active_product_count,
            metrics.sponsor_count,
        ),
        "score_reformulation_white_space": score_reformulation_white_space(
            metrics.route_diversity_count, metrics.dosage_form_diversity_count
        ),
    }
    completeness, confidence, evidence_notes = data_completeness(metrics)
    notes = [
        label
        for enabled, label in (
            (metrics.has_iv_only_or_injectable_only, "injectable-only"),
            (metrics.all_products_discontinued, "all products discontinued"),
            (metrics.mixed_active_discontinued, "mixed active/discontinued products"),
            (
                not metrics.latest_patent_expiry
                and not metrics.latest_exclusivity_expiry,
                "IP evidence unknown",
            ),
            (components["score_ip_openness"] == 3, "no future listed IP date"),
            (components["score_reformulation_white_space"] >= 2, "low formulation diversity"),
        )
        if enabled
    ]
    return {
        **components,
        "score_total": sum(components.values()),
        "score_confidence": confidence,
        "data_completeness_score": completeness,
        "phase1_notes": "; ".join(notes) or "no priority flag",
        "evidence_completeness_notes": evidence_notes,
    }
