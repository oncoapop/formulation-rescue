"""SQLite initialization and Phase 1 aggregation."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from .scoring import CandidateMetrics, score_candidate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "db" / "formulation_rescue.sqlite"
SCHEMA = PROJECT_ROOT / "db" / "schema.sql"


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(path: Path = DEFAULT_DB) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))


def _candidate_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        WITH patent_dates AS (
            SELECT product_id, MAX(patent_expiry) AS latest_patent_expiry
            FROM patents
            GROUP BY product_id
        ),
        exclusivity_dates AS (
            SELECT product_id, MAX(exclusivity_expiry) AS latest_exclusivity_expiry
            FROM exclusivities
            GROUP BY product_id
        )
        SELECT
            i.id AS ingredient_id,
            i.ingredient_name,
            COUNT(DISTINCT p.id) AS product_count,
            COUNT(DISTINCT NULLIF(TRIM(p.sponsor_name), '')) AS sponsor_count,
            COUNT(DISTINCT NULLIF(UPPER(TRIM(p.route)), '')) AS route_diversity_count,
            COUNT(DISTINCT NULLIF(UPPER(TRIM(p.dosage_form)), ''))
                AS dosage_form_diversity_count,
            MAX(pa.latest_patent_expiry) AS latest_patent_expiry,
            MAX(ex.latest_exclusivity_expiry) AS latest_exclusivity_expiry,
            MAX(p.is_discontinued) AS has_discontinued_product,
            CASE
                WHEN COUNT(DISTINCT p.id) > 0
                 AND SUM(CASE
                     WHEN UPPER(COALESCE(p.route, '')) LIKE '%INJECT%'
                       OR UPPER(COALESCE(p.route, '')) LIKE '%INTRAVENOUS%'
                     THEN 0 ELSE 1 END) = 0
                THEN 1 ELSE 0
            END AS has_iv_only_or_injectable_only
        FROM ingredients i
        JOIN product_ingredients pi ON pi.ingredient_id = i.id
        JOIN products p ON p.id = pi.product_id
        LEFT JOIN patent_dates pa ON pa.product_id = p.id
        LEFT JOIN exclusivity_dates ex ON ex.product_id = p.id
        GROUP BY i.id, i.ingredient_name
        ORDER BY i.ingredient_name
        """
    ).fetchall()


def score_phase1(path: Path = DEFAULT_DB, as_of: date | None = None) -> int:
    as_of = as_of or date.today()
    scored_at = datetime.now(timezone.utc).isoformat()
    with connect(path) as connection:
        rows = _candidate_rows(connection)
        connection.execute("DELETE FROM phase1_candidates")
        for row in rows:
            metrics = CandidateMetrics(
                ingredient_name=row["ingredient_name"],
                product_count=row["product_count"],
                sponsor_count=row["sponsor_count"],
                route_diversity_count=row["route_diversity_count"],
                dosage_form_diversity_count=row["dosage_form_diversity_count"],
                latest_patent_expiry=row["latest_patent_expiry"],
                latest_exclusivity_expiry=row["latest_exclusivity_expiry"],
                has_discontinued_product=bool(row["has_discontinued_product"]),
                has_iv_only_or_injectable_only=bool(
                    row["has_iv_only_or_injectable_only"]
                ),
            )
            scores = score_candidate(metrics, as_of)
            connection.execute(
                """
                INSERT INTO phase1_candidates VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    row["ingredient_id"],
                    row["ingredient_name"],
                    row["product_count"],
                    row["sponsor_count"],
                    row["route_diversity_count"],
                    row["dosage_form_diversity_count"],
                    row["latest_patent_expiry"],
                    row["latest_exclusivity_expiry"],
                    row["has_discontinued_product"],
                    row["has_iv_only_or_injectable_only"],
                    scores["score_ip_openness"],
                    scores["score_route_gap"],
                    scores["score_discontinued_or_fragile"],
                    scores["score_reformulation_white_space"],
                    scores["score_total"],
                    scores["phase1_notes"],
                    scored_at,
                ),
            )
    return len(rows)
