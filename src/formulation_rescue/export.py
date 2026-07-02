"""CSV and Markdown exports for Phase 1."""

from __future__ import annotations

import csv
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .database import DEFAULT_DB, PROJECT_ROOT, connect

DEFAULT_CSV = PROJECT_ROOT / "data" / "processed" / "phase1_candidates.csv"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "phase1_summary.md"

CSV_COLUMNS = (
    "ingredient_name",
    "product_count",
    "active_product_count",
    "discontinued_product_count",
    "tentative_or_nonmarketed_count",
    "unknown_marketing_status_count",
    "all_products_discontinued",
    "mixed_active_discontinued",
    "sponsor_count",
    "sponsor_list",
    "application_no_list",
    "application_type_list",
    "route_list_raw",
    "canonical_route_list",
    "dosage_form_list_raw",
    "canonical_dosage_form_list",
    "unknown_route_count",
    "unknown_dosage_form_count",
    "parenteral_route_signal",
    "latest_patent_expiry",
    "latest_exclusivity_expiry",
    "patent_count",
    "exclusivity_count",
    "delist_requested_signal",
    "pediatric_extension_signal",
    "source_conflict_flags",
    "mapping_quality_flags",
    "score_ip_openness",
    "score_route_gap",
    "score_discontinued_or_fragile",
    "score_reformulation_white_space",
    "score_confidence",
    "data_completeness_score",
    "score_total",
    "phase1_notes",
    "evidence_completeness_notes",
    "triage_class",
    "triage_subclass",
    "exclude_from_top_science_review",
    "exclusion_reason",
    "science_review_priority",
)


def export_phase1(
    db_path: Path = DEFAULT_DB,
    csv_path: Path = DEFAULT_CSV,
    report_path: Path = DEFAULT_REPORT,
    science_review_path: Path | None = None,
) -> int:
    with connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT {", ".join(CSV_COLUMNS)}
            FROM phase1_candidates
            ORDER BY score_total DESC, ingredient_name
            """
        ).fetchall()
        source_rows = connection.execute(
            """
            SELECT source_name, source_url, local_path, sha256, downloaded_at
            FROM source_files
            ORDER BY source_name, downloaded_at DESC
            """
        ).fetchall()
        totals = connection.execute(
            """
            SELECT
                (SELECT COUNT(DISTINCT product_id) FROM product_observations
                 WHERE active_in_latest_snapshot = 1) AS products,
                (SELECT COUNT(*) FROM phase1_candidates) AS ingredients,
                (SELECT COUNT(*) FROM patents
                 WHERE ip_active_in_latest_snapshot = 1) AS patents,
                (SELECT COUNT(*) FROM exclusivities
                 WHERE ip_active_in_latest_snapshot = 1) AS exclusivities
            """
        ).fetchone()
        triage_counts = connection.execute(
            """
            SELECT triage_class, COUNT(*) AS candidate_count
            FROM phase1_candidates
            GROUP BY triage_class
            ORDER BY candidate_count DESC, triage_class
            """
        ).fetchall()

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)

    science_review_path = science_review_path or csv_path.with_name(
        f"{csv_path.stem}_science_review.csv"
    )
    science_review_path.parent.mkdir(parents=True, exist_ok=True)
    with science_review_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(
            dict(row) for row in rows if not row["exclude_from_top_science_review"]
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    top_rows = rows[:20]
    scores = [row["score_total"] for row in rows]
    score_min = min(scores) if scores else None
    score_max = max(scores) if scores else None
    score_median = statistics.median(scores) if scores else None
    tied_at_max = sum(score == score_max for score in scores) if scores else 0
    buckets: dict[int, int] = {}
    for score in scores:
        buckets[score] = buckets.get(score, 0) + 1
    lines = [
        "# Phase 1 Screening Summary",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Candidates scored: {len(rows)}",
        f"Products: {totals['products']}",
        f"Ingredients: {totals['ingredients']}",
        f"Patents: {totals['patents']}",
        f"Exclusivities: {totals['exclusivities']}",
        "",
        "## Score distribution",
        "",
        f"- Minimum: {score_min if score_min is not None else 'n/a'}",
        f"- Maximum: {score_max if score_max is not None else 'n/a'}",
        f"- Median: {score_median if score_median is not None else 'n/a'}",
        f"- Candidates tied at maximum: {tied_at_max}",
        "- Count per score: "
        + (
            ", ".join(f"{score}={count}" for score, count in sorted(buckets.items()))
            if buckets
            else "none"
        ),
        "",
        "## Triage classes",
        "",
        "| Triage class | Candidates |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {row['triage_class']} | {row['candidate_count']} |"
        for row in triage_counts
    )
    lines.extend(
        [
            "",
            f"Science-review candidates retained: "
            f"{sum(not row['exclude_from_top_science_review'] for row in rows)}",
            "",
        "## Highest-scoring candidates",
        "",
        "| Ingredient | Score | Confidence | Active | Discontinued | Notes |",
        "|---|---:|---|---:|---:|---|",
        ]
    )
    lines.extend(
        "| {ingredient_name} | {score_total} | {score_confidence} | "
        "{active_product_count} | {discontinued_product_count} | "
        "{phase1_notes} |".format(
            **{key: str(row[key]).replace("|", r"\|") for key in row.keys()}
        )
        for row in top_rows
    )
    if not top_rows:
        lines.append("| _No candidates_ | — | — | — | — | — |")
    lines.extend(["", "## Source files", ""])
    if source_rows:
        for source in source_rows:
            lines.append(
                f"- {source['source_name']}: `{source['local_path']}` "
                f"(SHA256 `{source['sha256']}`, timestamp {source['downloaded_at']}; "
                f"{source['source_url']})"
            )
    else:
        lines.append("- No source files recorded.")
    lines.extend(
        [
            "",
            "## Method",
            "",
            "Scores are deterministic screening heuristics for IP openness, "
            "route gap, discontinued/sponsor fragility, and dosage-form diversity. "
            "Missing IP evidence is treated as unknown. All-products-discontinued "
            "and mixed active/discontinued portfolios are scored differently. "
            "Confidence reflects completeness of core FDA evidence, not scientific "
            "or commercial certainty. Ingredient matching only normalizes case and "
            "whitespace; it does not infer synonyms, salts, or chemical equivalence.",
            "",
            "Screening output only; not legal, regulatory, investment, or medical advice.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)
