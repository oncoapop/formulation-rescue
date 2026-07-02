"""SQLite initialization and Phase 1 aggregation."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from .scoring import CandidateMetrics, score_candidate
from .triage import classify_candidate

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
        _migrate_database(connection)


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}


def _add_columns(
    connection: sqlite3.Connection, table: str, definitions: dict[str, str]
) -> None:
    existing = _columns(connection, table)
    for name, definition in definitions.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _migrate_database(connection: sqlite3.Connection) -> None:
    """Apply additive migrations and recreate the fully derived candidate table."""
    _add_columns(
        connection,
        "product_ingredients",
        {
            "raw_active_ingredient": "TEXT",
            "raw_strength": "TEXT",
            "mapping_quality": "TEXT NOT NULL DEFAULT 'unknown'",
        },
    )
    _add_columns(
        connection,
        "patents",
        {
            "ip_active_in_latest_snapshot": "INTEGER NOT NULL DEFAULT 1",
            "ip_first_seen_at": "TEXT",
            "ip_last_seen_at": "TEXT",
            "delist_requested_signal": "INTEGER NOT NULL DEFAULT 0",
            "pediatric_extension_signal": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    _add_columns(
        connection,
        "product_observations",
        {"parenteral_route_signal": "INTEGER NOT NULL DEFAULT 0"},
    )
    _add_columns(
        connection,
        "exclusivities",
        {
            "ip_active_in_latest_snapshot": "INTEGER NOT NULL DEFAULT 1",
            "ip_first_seen_at": "TEXT",
            "ip_last_seen_at": "TEXT",
            "pediatric_extension_signal": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    required = {
        "active_product_count",
        "canonical_route_list",
        "score_confidence",
        "evidence_completeness_notes",
        "triage_class",
    }
    if not required.issubset(_columns(connection, "phase1_candidates")):
        connection.execute("DROP TABLE phase1_candidates")
        schema = SCHEMA.read_text(encoding="utf-8")
        start = schema.index("CREATE TABLE IF NOT EXISTS phase1_candidates")
        end = schema.index("CREATE INDEX", start)
        connection.executescript(schema[start:end])


def _sorted_join(values: set[str]) -> str:
    return "; ".join(sorted(value for value in values if value))


def _candidate_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    current = connection.execute(
        """
        WITH ranked AS (
            SELECT po.*,
                ROW_NUMBER() OVER (
                    PARTITION BY po.product_id
                    ORDER BY CASE po.source_name
                        WHEN 'Drugs@FDA' THEN 0 ELSE 1 END,
                        po.observed_at DESC
                ) AS priority
            FROM product_observations po
            WHERE po.active_in_latest_snapshot = 1
        )
        SELECT
            i.id AS ingredient_id,
            i.ingredient_name,
            p.id AS product_id,
            p.application_number,
            r.application_type,
            r.sponsor_name,
            r.dosage_form_raw,
            r.route_raw,
            r.canonical_dosage_form,
            r.canonical_route,
            r.parenteral_route_signal,
            r.unknown_dosage_form,
            r.unknown_route,
            r.marketing_status_class,
            r.mapping_quality
        FROM ranked r
        JOIN products p ON p.id = r.product_id
        JOIN product_ingredients pi ON pi.product_id = p.id
        JOIN ingredients i ON i.id = pi.ingredient_id
        WHERE r.priority = 1
        ORDER BY i.ingredient_name, p.application_number, p.product_number
        """
    ).fetchall()

    conflicts: dict[int, set[str]] = defaultdict(set)
    observations: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for observation in connection.execute(
        """
        SELECT product_id, source_name, marketing_status_class, canonical_route
        FROM product_observations
        WHERE active_in_latest_snapshot = 1
        """
    ):
        observations[observation["product_id"]].append(observation)
    for product_id, values in observations.items():
        statuses = {
            row["marketing_status_class"]
            for row in values
            if row["marketing_status_class"] != "unknown"
        }
        routes = {row["canonical_route"] for row in values if row["canonical_route"]}
        if len(statuses) > 1:
            conflicts[product_id].add("marketing_status_disagreement")
        if len(routes) > 1:
            conflicts[product_id].add("route_disagreement")

    ip_by_product: dict[int, dict[str, object]] = defaultdict(
        lambda: {
            "patent_dates": [],
            "exclusivity_dates": [],
            "patent_count": 0,
            "exclusivity_count": 0,
            "delist": 0,
            "pediatric": 0,
        }
    )
    for row in connection.execute(
        """
        SELECT product_id, patent_expiry, delist_requested_signal,
               pediatric_extension_signal
        FROM patents WHERE ip_active_in_latest_snapshot = 1
        """
    ):
        evidence = ip_by_product[row["product_id"]]
        evidence["patent_count"] += 1
        if row["patent_expiry"]:
            evidence["patent_dates"].append(row["patent_expiry"])
        evidence["delist"] = max(evidence["delist"], row["delist_requested_signal"])
        evidence["pediatric"] = max(
            evidence["pediatric"], row["pediatric_extension_signal"]
        )
    for row in connection.execute(
        """
        SELECT product_id, exclusivity_expiry, pediatric_extension_signal
        FROM exclusivities WHERE ip_active_in_latest_snapshot = 1
        """
    ):
        evidence = ip_by_product[row["product_id"]]
        evidence["exclusivity_count"] += 1
        if row["exclusivity_expiry"]:
            evidence["exclusivity_dates"].append(row["exclusivity_expiry"])
        evidence["pediatric"] = max(
            evidence["pediatric"], row["pediatric_extension_signal"]
        )

    grouped: dict[int, dict[str, object]] = {}
    for row in current:
        candidate = grouped.setdefault(
            row["ingredient_id"],
            {
                "ingredient_id": row["ingredient_id"],
                "ingredient_name": row["ingredient_name"],
                "products": set(),
                "statuses": {},
                "sponsors": set(),
                "applications": set(),
                "application_types": set(),
                "routes_raw": set(),
                "routes": set(),
                "forms_raw": set(),
                "forms": set(),
                "unknown_routes": set(),
                "unknown_forms": set(),
                "parenteral_products": set(),
                "conflicts": set(),
                "mapping_quality": set(),
                "patent_dates": [],
                "exclusivity_dates": [],
                "patent_count": 0,
                "exclusivity_count": 0,
                "delist": 0,
                "pediatric": 0,
                "ip_products": set(),
            },
        )
        product_id = row["product_id"]
        if product_id in candidate["products"]:
            continue
        candidate["products"].add(product_id)
        candidate["statuses"][product_id] = row["marketing_status_class"]
        candidate["sponsors"].add(row["sponsor_name"] or "")
        candidate["applications"].add(row["application_number"])
        application_type = (row["application_type"] or "").upper()
        if application_type == "N":
            application_type = "NDA"
        elif application_type == "A":
            application_type = "ANDA"
        candidate["application_types"].add(application_type)
        candidate["routes_raw"].add(row["route_raw"] or "")
        candidate["forms_raw"].add(row["dosage_form_raw"] or "")
        candidate["forms"].add(row["canonical_dosage_form"] or "")
        for route in (row["canonical_route"] or "").split(";"):
            candidate["routes"].add(route.strip())
        if row["unknown_route"]:
            candidate["unknown_routes"].add(product_id)
        if row["unknown_dosage_form"]:
            candidate["unknown_forms"].add(product_id)
        if row["parenteral_route_signal"]:
            candidate["parenteral_products"].add(product_id)
        candidate["mapping_quality"].add(row["mapping_quality"])
        candidate["conflicts"].update(conflicts[product_id])
        if row["application_number"].startswith("FDA"):
            candidate["conflicts"].add("missing_application_type")
        evidence = ip_by_product[product_id]
        if product_id not in candidate["ip_products"]:
            candidate["ip_products"].add(product_id)
            candidate["patent_dates"].extend(evidence["patent_dates"])
            candidate["exclusivity_dates"].extend(evidence["exclusivity_dates"])
            candidate["patent_count"] += evidence["patent_count"]
            candidate["exclusivity_count"] += evidence["exclusivity_count"]
            candidate["delist"] = max(candidate["delist"], evidence["delist"])
            candidate["pediatric"] = max(
                candidate["pediatric"], evidence["pediatric"]
            )

    result: list[dict[str, object]] = []
    for candidate in grouped.values():
        statuses = list(candidate["statuses"].values())
        active = statuses.count("active")
        discontinued = statuses.count("discontinued")
        nonmarketed = statuses.count("tentative_or_nonmarketed")
        unknown = statuses.count("unknown")
        product_count = len(candidate["products"])
        all_discontinued = discontinued == product_count and product_count > 0
        mixed = active > 0 and discontinued > 0
        routes = {value for value in candidate["routes"] if value}
        forms = {value for value in candidate["forms"] if value}
        parenteral_only = (
            bool(routes)
            and not candidate["unknown_routes"]
            and len(candidate["parenteral_products"]) == product_count
        )
        result.append(
            {
                "ingredient_id": candidate["ingredient_id"],
                "ingredient_name": candidate["ingredient_name"],
                "product_count": product_count,
                "active_product_count": active,
                "discontinued_product_count": discontinued,
                "tentative_or_nonmarketed_count": nonmarketed,
                "unknown_marketing_status_count": unknown,
                "all_products_discontinued": int(all_discontinued),
                "mixed_active_discontinued": int(mixed),
                "sponsor_count": len(
                    {value for value in candidate["sponsors"] if value}
                ),
                "sponsor_list": _sorted_join(candidate["sponsors"]),
                "application_no_list": _sorted_join(candidate["applications"]),
                "application_type_list": _sorted_join(
                    candidate["application_types"]
                ),
                "route_list_raw": _sorted_join(candidate["routes_raw"]),
                "canonical_route_list": _sorted_join(routes),
                "dosage_form_list_raw": _sorted_join(candidate["forms_raw"]),
                "canonical_dosage_form_list": _sorted_join(forms),
                "unknown_route_count": len(candidate["unknown_routes"]),
                "unknown_dosage_form_count": len(candidate["unknown_forms"]),
                "parenteral_route_signal": int(bool(candidate["parenteral_products"])),
                "route_diversity_count": len(routes),
                "dosage_form_diversity_count": len(forms),
                "latest_patent_expiry": (
                    max(candidate["patent_dates"])
                    if candidate["patent_dates"]
                    else None
                ),
                "latest_exclusivity_expiry": (
                    max(candidate["exclusivity_dates"])
                    if candidate["exclusivity_dates"]
                    else None
                ),
                "patent_count": candidate["patent_count"],
                "exclusivity_count": candidate["exclusivity_count"],
                "delist_requested_signal": candidate["delist"],
                "pediatric_extension_signal": candidate["pediatric"],
                "source_conflict_flags": _sorted_join(candidate["conflicts"]),
                "mapping_quality_flags": _sorted_join(
                    candidate["mapping_quality"]
                ),
                "has_discontinued_product": int(discontinued > 0),
                "has_iv_only_or_injectable_only": int(parenteral_only),
            }
        )
    return sorted(result, key=lambda row: row["ingredient_name"])


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
                active_product_count=row["active_product_count"],
                discontinued_product_count=row["discontinued_product_count"],
                tentative_or_nonmarketed_count=row[
                    "tentative_or_nonmarketed_count"
                ],
                unknown_marketing_status_count=row[
                    "unknown_marketing_status_count"
                ],
                all_products_discontinued=bool(row["all_products_discontinued"]),
                mixed_active_discontinued=bool(row["mixed_active_discontinued"]),
                sponsor_count=row["sponsor_count"],
                route_diversity_count=row["route_diversity_count"],
                dosage_form_diversity_count=row["dosage_form_diversity_count"],
                latest_patent_expiry=row["latest_patent_expiry"],
                latest_exclusivity_expiry=row["latest_exclusivity_expiry"],
                has_discontinued_product=bool(row["has_discontinued_product"]),
                has_iv_only_or_injectable_only=bool(
                    row["has_iv_only_or_injectable_only"]
                ),
                parenteral_route_signal=bool(row["parenteral_route_signal"]),
                patent_count=row["patent_count"],
                exclusivity_count=row["exclusivity_count"],
                unknown_route_count=row["unknown_route_count"],
                unknown_dosage_form_count=row["unknown_dosage_form_count"],
                source_conflict_flags=row["source_conflict_flags"],
                mapping_quality_flags=row["mapping_quality_flags"],
            )
            scores = score_candidate(metrics, as_of)
            triage = classify_candidate(row, int(scores["score_total"]))
            values = {
                **row,
                **scores,
                "triage_class": triage.triage_class,
                "triage_subclass": triage.triage_subclass,
                "exclude_from_top_science_review": int(
                    triage.exclude_from_top_science_review
                ),
                "exclusion_reason": triage.exclusion_reason,
                "science_review_priority": triage.science_review_priority,
                "scored_at": scored_at,
            }
            columns = tuple(values)
            connection.execute(
                f"""
                INSERT INTO phase1_candidates ({", ".join(columns)})
                VALUES ({", ".join("?" for _ in columns)})
                """,
                tuple(values[column] for column in columns),
            )
    return len(rows)
