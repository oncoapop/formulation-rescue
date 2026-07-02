"""CSV and Markdown exports for Phase 1."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from .database import DEFAULT_DB, PROJECT_ROOT, connect

DEFAULT_CSV = PROJECT_ROOT / "data" / "processed" / "phase1_candidates.csv"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "phase1_summary.md"

CSV_COLUMNS = (
    "ingredient_name",
    "product_count",
    "sponsor_count",
    "route_diversity_count",
    "dosage_form_diversity_count",
    "latest_patent_expiry",
    "latest_exclusivity_expiry",
    "has_discontinued_product",
    "has_iv_only_or_injectable_only",
    "score_ip_openness",
    "score_route_gap",
    "score_discontinued_or_fragile",
    "score_reformulation_white_space",
    "score_total",
    "phase1_notes",
)


def export_phase1(
    db_path: Path = DEFAULT_DB,
    csv_path: Path = DEFAULT_CSV,
    report_path: Path = DEFAULT_REPORT,
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
                (SELECT COUNT(*) FROM products) AS products,
                (SELECT COUNT(*) FROM ingredients) AS ingredients,
                (SELECT COUNT(*) FROM patents) AS patents,
                (SELECT COUNT(*) FROM exclusivities) AS exclusivities
            """
        ).fetchone()

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    top_rows = rows[:10]
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
        "## Highest-scoring candidates",
        "",
        "| Ingredient | Score | Products | Sponsors | Notes |",
        "|---|---:|---:|---:|---|",
    ]
    lines.extend(
        "| {ingredient_name} | {score_total} | {product_count} | "
        "{sponsor_count} | {phase1_notes} |".format(
            **{key: str(row[key]).replace("|", r"\|") for key in row.keys()}
        )
        for row in top_rows
    )
    if not top_rows:
        lines.append("| _No candidates_ | — | — | — | — |")
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
            "Scores are deterministic 0–3 component heuristics for IP openness, "
            "route gap, discontinued/sponsor fragility, and formulation diversity. "
            "Ingredient matching only normalizes case and whitespace; it does not "
            "infer synonyms, salts, or chemical equivalence.",
            "",
            "Screening output only; not legal, regulatory, investment, or medical advice.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)
