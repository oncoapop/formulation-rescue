"""DailyMed label retrieval, evidence extraction, scoring, and export."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .database import DEFAULT_DB, PROJECT_ROOT, connect, initialize_database
from .export import CSV_COLUMNS

DAILYMED_API = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
DEFAULT_SCIENCE_REVIEW_CSV = (
    PROJECT_ROOT / "data" / "processed" / "phase1_candidates_science_review.csv"
)
DEFAULT_DAILYMED_RAW = PROJECT_ROOT / "data" / "raw" / "dailymed"
DEFAULT_ENRICHED_CSV = (
    PROJECT_ROOT / "data" / "processed" / "phase3_label_enriched_candidates.csv"
)
DEFAULT_SIGNALS_CSV = (
    PROJECT_ROOT / "data" / "processed" / "top_scientific_rescue_signals.csv"
)
DEFAULT_PHASE3_REPORT = PROJECT_ROOT / "reports" / "phase3_label_enrichment_summary.md"

LABEL_COLUMNS = (
    "retrieval_status",
    "has_boxed_warning",
    "has_serious_warning_signal",
    "has_infusion_or_injection_reaction_signal",
    "has_hypersensitivity_signal",
    "has_reconstitution_signal",
    "has_special_preparation_signal",
    "has_storage_burden_signal",
    "has_light_protection_signal",
    "has_refrigeration_signal",
    "has_short_post_reconstitution_stability_signal",
    "has_pediatric_gap_signal",
    "has_renal_hepatic_adjustment_signal",
    "administration_burden_terms",
    "safety_burden_terms",
    "formulation_burden_terms",
    "label_match_quality",
    "label_source_setid_or_id",
    "label_last_updated_if_available",
    "score_administration_burden",
    "score_safety_burden",
    "score_formulation_handling_burden",
    "score_pediatric_gap",
    "score_route_conversion_opportunity",
    "score_label_evidence_confidence",
    "scientific_rescue_signal_score",
    "scientific_review_rationale",
)

SIGNAL_COLUMNS = (
    "ingredient_name",
    "triage_class",
    "triage_subclass",
    "science_review_priority",
    "product_count",
    "active_product_count",
    "discontinued_product_count",
    "all_products_discontinued",
    "mixed_active_discontinued",
    "canonical_route_list",
    "canonical_dosage_form_list",
    "parenteral_route_signal",
    "score_total",
    "score_administration_burden",
    "score_safety_burden",
    "score_formulation_handling_burden",
    "score_pediatric_gap",
    "score_route_conversion_opportunity",
    "score_label_evidence_confidence",
    "scientific_rescue_signal_score",
    "label_match_quality",
    "administration_burden_terms",
    "safety_burden_terms",
    "formulation_burden_terms",
    "phase1_notes",
    "evidence_completeness_notes",
    "scientific_review_rationale",
)

_SALT_WORDS = {
    "acetate",
    "chloride",
    "hydrochloride",
    "mesylate",
    "phosphate",
    "sodium",
    "sulfate",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_stem(ingredient: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", ingredient.casefold()).strip("-")[:60]
    digest = hashlib.sha256(ingredient.encode("utf-8")).hexdigest()[:12]
    return f"{slug or 'ingredient'}-{digest}"


def _normalized_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def label_match_quality(ingredient: str, title: str) -> str:
    ingredient_words = _normalized_words(ingredient)
    title_words = _normalized_words(title)
    if not title_words:
        return "no_match"
    ingredient_phrase = " ".join(ingredient_words)
    title_phrase = " ".join(title_words)
    if ingredient_phrase and ingredient_phrase in title_phrase:
        return "exact"
    meaningful = [word for word in ingredient_words if word not in _SALT_WORDS]
    if meaningful and all(word in title_words for word in meaningful):
        return "high"
    if meaningful and sum(word in title_words for word in meaningful) >= max(
        1, len(meaningful) // 2
    ):
        return "low"
    return "no_match"


def _select_metadata_match(
    ingredient: str, records: Iterable[Mapping[str, object]]
) -> tuple[dict[str, object] | None, str]:
    ranked = []
    quality_rank = {"exact": 3, "high": 2, "low": 1, "no_match": 0}
    for index, record in enumerate(records):
        quality = label_match_quality(ingredient, str(record.get("title", "")))
        ranked.append((quality_rank[quality], -index, dict(record), quality))
    if not ranked:
        return None, "no_match"
    _, _, selected, quality = max(ranked)
    return (selected, quality) if quality != "no_match" else (None, "no_match")


def _request_bytes(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "formulation-rescue/0.3 (public DailyMed research)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download_dailymed_labels(
    input_csv: Path = DEFAULT_SCIENCE_REVIEW_CSV,
    raw_dir: Path = DEFAULT_DAILYMED_RAW,
    *,
    limit: int | None = None,
    refresh: bool = False,
    delay_seconds: float = 0.1,
) -> dict[str, int]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    with input_csv.open(newline="", encoding="utf-8") as handle:
        candidates = list(csv.DictReader(handle))
    if limit is not None:
        candidates = candidates[:limit]
    counts = Counter()
    for candidate in candidates:
        ingredient = candidate["ingredient_name"]
        directory = raw_dir / _safe_stem(ingredient)
        manifest_path = directory / "manifest.json"
        if manifest_path.exists() and not refresh:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") in {"matched", "no_match"}:
                counts["cached"] += 1
                counts[manifest["status"]] += 1
                continue
        directory.mkdir(parents=True, exist_ok=True)
        query = urllib.parse.urlencode(
            {
                "drug_name": ingredient,
                "name_type": "generic",
                "pagesize": 10,
                "page": 1,
            }
        )
        metadata_url = f"{DAILYMED_API}/spls.json?{query}"
        try:
            metadata_bytes = _request_bytes(metadata_url)
            metadata_path = directory / "metadata.json"
            metadata_path.write_bytes(metadata_bytes)
            payload = json.loads(metadata_bytes)
            selected, quality = _select_metadata_match(
                ingredient, payload.get("data", [])
            )
            if selected is None:
                manifest = {
                    "ingredient_name": ingredient,
                    "status": "no_match",
                    "label_match_quality": "no_match",
                    "metadata_url": metadata_url,
                    "metadata_path": str(metadata_path.resolve()),
                    "retrieved_at": _now(),
                }
                counts["no_match"] += 1
            else:
                setid = str(selected["setid"])
                label_url = f"{DAILYMED_API}/spls/{setid}.xml"
                label_bytes = _request_bytes(label_url)
                label_path = directory / "label.xml"
                label_path.write_bytes(label_bytes)
                manifest = {
                    "ingredient_name": ingredient,
                    "status": "matched",
                    "label_match_quality": quality,
                    "setid": setid,
                    "title": selected.get("title", ""),
                    "published_date": selected.get("published_date", ""),
                    "metadata_url": metadata_url,
                    "label_url": label_url,
                    "metadata_path": str(metadata_path.resolve()),
                    "label_path": str(label_path.resolve()),
                    "retrieved_at": _now(),
                }
                counts["matched"] += 1
                counts[quality] += 1
            temporary = manifest_path.with_suffix(".json.part")
            temporary.write_text(
                json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
            )
            os.replace(temporary, manifest_path)
        except (OSError, urllib.error.URLError, ValueError, KeyError, ET.ParseError):
            counts["errors"] += 1
        if delay_seconds:
            time.sleep(delay_seconds)
    counts["attempted"] = len(candidates)
    return dict(counts)


def xml_label_text(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)
    chunks = [" ".join(text.split()) for text in root.itertext() if text.strip()]
    if any(element.attrib.get("code") == "34066-1" for element in root.iter()):
        chunks.append("__BOXED_WARNING_SECTION__")
    return "\n".join(chunks)


def _matched_terms(text: str, patterns: Mapping[str, str]) -> list[str]:
    return [
        label
        for label, pattern in patterns.items()
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def extract_label_evidence(text: str) -> dict[str, object]:
    normalized = " ".join(text.split())
    administration = _matched_terms(
        normalized,
        {
            "infusion administration": r"\binfus(?:ion|e|ed)\b",
            "injection administration": r"\binject(?:ion|able|ed)?\b",
            "slow administration": r"\badminister(?:ed)? (?:slowly|over \d+)",
            "administration monitoring": r"\bmonitor.{0,50}(?:during|after) administration\b",
        },
    )
    safety = _matched_terms(
        normalized,
        {
            "boxed warning": r"\bboxed warning\b|\bblack box warning\b|__BOXED_WARNING_SECTION__",
            "serious or fatal warning": r"\b(?:serious|life-threatening|fatal) (?:adverse|reaction|risk|event)",
            "hypersensitivity": r"\bhypersensitiv|\banaphyl",
            "infusion or injection reaction": r"\b(?:infusion|injection)[ -](?:related )?reaction",
        },
    )
    formulation = _matched_terms(
        normalized,
        {
            "reconstitution": r"\breconstitut",
            "dilution": r"\bdilut(?:e|ed|ion)",
            "special preparation": r"\b(?:aseptic technique|prepare immediately|special preparation)\b",
            "storage requirements": r"\b(?:store|storage|discard|use within)\b",
            "light protection": r"\bprotect from light\b",
            "refrigeration": r"\brefrigerat|\b2\s*(?:°|degrees?)?\s*c\s*(?:to|-)\s*8",
            "short post-reconstitution stability": r"\buse within (?:[1-9]|[1-3]\d|4[0-8]) (?:hours?|hrs?)\b",
        },
    )
    pediatric = bool(
        re.search(
            r"(?:(?:safety and effectiveness|use).{0,80}(?:pediatric|children).{0,80}"
            r"(?:not been established|not established|unknown)|"
            r"(?:pediatric|children).{0,80}(?:safety and effectiveness|use).{0,80}"
            r"(?:not been established|not established|unknown))",
            normalized,
            flags=re.IGNORECASE,
        )
    )
    renal_hepatic = bool(
        re.search(
            r"\b(?:renal|hepatic) (?:impairment|adjustment|dose adjustment)\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )
    return {
        "has_boxed_warning": int("boxed warning" in safety),
        "has_serious_warning_signal": int(
            "serious or fatal warning" in safety or "boxed warning" in safety
        ),
        "has_infusion_or_injection_reaction_signal": int(
            "infusion or injection reaction" in safety
        ),
        "has_hypersensitivity_signal": int("hypersensitivity" in safety),
        "has_reconstitution_signal": int("reconstitution" in formulation),
        "has_special_preparation_signal": int(
            bool(
                {"reconstitution", "dilution", "special preparation"}
                & set(formulation)
            )
        ),
        "has_storage_burden_signal": int("storage requirements" in formulation),
        "has_light_protection_signal": int("light protection" in formulation),
        "has_refrigeration_signal": int("refrigeration" in formulation),
        "has_short_post_reconstitution_stability_signal": int(
            "short post-reconstitution stability" in formulation
        ),
        "has_pediatric_gap_signal": int(pediatric),
        "has_renal_hepatic_adjustment_signal": int(renal_hepatic),
        "administration_burden_terms": "; ".join(administration),
        "safety_burden_terms": "; ".join(safety),
        "formulation_burden_terms": "; ".join(formulation),
    }


def _empty_evidence() -> dict[str, object]:
    evidence = extract_label_evidence("")
    return evidence


def ingest_dailymed_labels(
    raw_dir: Path = DEFAULT_DAILYMED_RAW,
    db_path: Path = DEFAULT_DB,
) -> dict[str, int]:
    initialize_database(db_path)
    counts = Counter()
    manifests = sorted(raw_dir.glob("*/manifest.json")) if raw_dir.exists() else []
    with connect(db_path) as connection:
        ingredients = {
            row["ingredient_name"].casefold(): row["id"]
            for row in connection.execute("SELECT id, ingredient_name FROM ingredients")
        }
        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            ingredient_name = manifest.get("ingredient_name", "")
            ingredient_id = ingredients.get(ingredient_name.casefold())
            if ingredient_id is None:
                counts["unmapped"] += 1
                continue
            status = manifest.get("status", "error")
            evidence = _empty_evidence()
            if status == "matched":
                label_path = Path(manifest["label_path"])
                evidence = extract_label_evidence(
                    xml_label_text(label_path.read_bytes())
                )
                counts["matched"] += 1
            else:
                counts[status] += 1
            values = {
                "ingredient_id": ingredient_id,
                "ingredient_name": ingredient_name,
                "retrieval_status": status,
                "label_match_quality": manifest.get(
                    "label_match_quality", "no_match"
                ),
                "label_source_setid_or_id": manifest.get("setid", ""),
                "label_title": manifest.get("title", ""),
                "label_last_updated_if_available": manifest.get(
                    "published_date", ""
                ),
                "metadata_path": manifest.get("metadata_path", ""),
                "label_path": manifest.get("label_path", ""),
                **evidence,
                "ingested_at": _now(),
            }
            columns = tuple(values)
            updates = ", ".join(
                f"{column}=excluded.{column}"
                for column in columns
                if column != "ingredient_id"
            )
            connection.execute(
                f"""
                INSERT INTO dailymed_label_evidence ({", ".join(columns)})
                VALUES ({", ".join("?" for _ in columns)})
                ON CONFLICT(ingredient_id) DO UPDATE SET {updates}
                """,
                tuple(values[column] for column in columns),
            )
    counts["manifests"] = len(manifests)
    return dict(counts)


def label_component_scores(
    evidence: Mapping[str, object], candidate: Mapping[str, object]
) -> dict[str, int]:
    administration = min(
        3,
        int(bool(evidence.get("administration_burden_terms")))
        + int(bool(evidence.get("has_infusion_or_injection_reaction_signal")))
        + int(bool(evidence.get("has_special_preparation_signal"))),
    )
    safety = min(
        3,
        2 * int(bool(evidence.get("has_boxed_warning")))
        + int(bool(evidence.get("has_serious_warning_signal")))
        + int(bool(evidence.get("has_hypersensitivity_signal"))),
    )
    formulation = min(
        3,
        int(bool(evidence.get("has_reconstitution_signal")))
        + int(bool(evidence.get("has_storage_burden_signal")))
        + int(
            bool(evidence.get("has_light_protection_signal"))
            or bool(evidence.get("has_refrigeration_signal"))
            or bool(evidence.get("has_short_post_reconstitution_stability_signal"))
        ),
    )
    pediatric = 2 if evidence.get("has_pediatric_gap_signal") else 0
    route_conversion = min(
        3,
        2 * int(bool(candidate.get("parenteral_route_signal")))
        + int(administration >= 2 or formulation >= 2),
    )
    confidence = {
        "exact": 3,
        "high": 2,
        "low": 1,
    }.get(str(evidence.get("label_match_quality", "")), 0)
    return {
        "score_administration_burden": administration,
        "score_safety_burden": safety,
        "score_formulation_handling_burden": formulation,
        "score_pediatric_gap": pediatric,
        "score_route_conversion_opportunity": route_conversion,
        "score_label_evidence_confidence": confidence,
    }


def combined_scientific_score(
    candidate: Mapping[str, object],
    evidence: Mapping[str, object],
    scores: Mapping[str, int],
) -> tuple[int, str]:
    priority = {"high": 3, "medium": 2, "low": 1, "excluded": 0}.get(
        str(candidate.get("science_review_priority", "")), 0
    )
    total = (
        priority
        + 2 * int(bool(candidate.get("parenteral_route_signal")))
        + 2 * int(bool(candidate.get("all_products_discontinued")))
        + int(bool(candidate.get("mixed_active_discontinued")))
        + sum(scores.values())
        + round(int(candidate.get("data_completeness_score", 0)) / 50)
    )
    reasons = []
    if candidate.get("parenteral_route_signal"):
        reasons.append("parenteral route with route-conversion potential")
    if candidate.get("all_products_discontinued"):
        reasons.append("all recorded products discontinued")
    elif candidate.get("mixed_active_discontinued"):
        reasons.append("mixed active/discontinued products")
    if scores["score_formulation_handling_burden"]:
        reasons.append("label describes formulation-handling burden")
    if scores["score_administration_burden"]:
        reasons.append("label describes administration burden")
    if scores["score_safety_burden"]:
        reasons.append("label describes safety/tolerability burden")
    triage_class = str(candidate.get("triage_class", ""))
    if candidate.get("exclude_from_top_science_review"):
        total -= 10
        reasons.append("excluded triage class penalty")
    if triage_class in {
        "diagnostic_agent",
        "radiopharmaceutical",
        "contrast_agent",
        "device_like_or_procedure_agent",
    }:
        total -= 5
    quality = str(evidence.get("label_match_quality", "no_match"))
    if quality in {"no_match", "not_attempted", ""}:
        total -= 6
        reasons.append("missing DailyMed label evidence")
    elif quality == "low":
        total -= 2
        reasons.append("low-quality DailyMed match")
    return max(0, total), "; ".join(reasons) or "limited rescue evidence"


def score_label_burden(db_path: Path = DEFAULT_DB) -> int:
    initialize_database(db_path)
    with connect(db_path) as connection:
        candidates = connection.execute("SELECT * FROM phase1_candidates").fetchall()
        existing = {
            row["ingredient_id"]: dict(row)
            for row in connection.execute("SELECT * FROM dailymed_label_evidence")
        }
        for row in candidates:
            candidate = dict(row)
            evidence = existing.get(row["ingredient_id"])
            if evidence is None:
                evidence = {
                    "ingredient_id": row["ingredient_id"],
                    "ingredient_name": row["ingredient_name"],
                    "retrieval_status": "not_attempted",
                    "label_match_quality": "not_attempted",
                    **_empty_evidence(),
                }
            scores = label_component_scores(evidence, candidate)
            combined, rationale = combined_scientific_score(
                candidate, evidence, scores
            )
            values = {
                **evidence,
                **scores,
                "scientific_rescue_signal_score": combined,
                "scientific_review_rationale": rationale,
                "ingested_at": evidence.get("ingested_at", _now()),
            }
            allowed = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(dailymed_label_evidence)"
                )
            }
            values = {key: value for key, value in values.items() if key in allowed}
            columns = tuple(values)
            updates = ", ".join(
                f"{column}=excluded.{column}"
                for column in columns
                if column != "ingredient_id"
            )
            connection.execute(
                f"""
                INSERT INTO dailymed_label_evidence ({", ".join(columns)})
                VALUES ({", ".join("?" for _ in columns)})
                ON CONFLICT(ingredient_id) DO UPDATE SET {updates}
                """,
                tuple(values[column] for column in columns),
            )
    return len(candidates)


def export_scientific_rescue_signals(
    db_path: Path = DEFAULT_DB,
    enriched_path: Path = DEFAULT_ENRICHED_CSV,
    signals_path: Path = DEFAULT_SIGNALS_CSV,
    report_path: Path = DEFAULT_PHASE3_REPORT,
    *,
    limit: int = 100,
) -> dict[str, int]:
    with connect(db_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                f"""
                SELECT {", ".join(f"c.{column}" for column in CSV_COLUMNS)},
                       {", ".join(f"d.{column}" for column in LABEL_COLUMNS)}
                FROM phase1_candidates c
                LEFT JOIN dailymed_label_evidence d
                  ON d.ingredient_id = c.ingredient_id
                ORDER BY COALESCE(d.scientific_rescue_signal_score, 0) DESC,
                         c.data_completeness_score DESC,
                         c.ingredient_name
                """
            )
        ]
    defaults = {
        column: (
            "not_attempted"
            if column in {"retrieval_status", "label_match_quality"}
            else ""
            if column.endswith("terms")
            or column
            in {
                "label_source_setid_or_id",
                "label_last_updated_if_available",
                "scientific_review_rationale",
            }
            else 0
        )
        for column in LABEL_COLUMNS
    }
    for row in rows:
        for column, default in defaults.items():
            if row[column] is None:
                row[column] = default
    enriched_columns = CSV_COLUMNS + LABEL_COLUMNS
    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    with enriched_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=enriched_columns)
        writer.writeheader()
        writer.writerows(rows)

    shortlisted = [
        row
        for row in rows
        if not row["exclude_from_top_science_review"]
        and row["label_match_quality"] in {"exact", "high"}
        and row["scientific_rescue_signal_score"] >= 10
        and (
            row["score_administration_burden"]
            + row["score_safety_burden"]
            + row["score_formulation_handling_burden"]
            + row["score_pediatric_gap"]
            > 0
        )
    ][:limit]
    signals_path.parent.mkdir(parents=True, exist_ok=True)
    with signals_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SIGNAL_COLUMNS)
        writer.writeheader()
        writer.writerows(
            {column: row[column] for column in SIGNAL_COLUMNS} for row in shortlisted
        )

    attempted = [row for row in rows if row["retrieval_status"] != "not_attempted"]
    matched = [row for row in attempted if row["retrieval_status"] == "matched"]
    quality_counts = Counter(row["label_match_quality"] for row in attempted)
    flag_columns = [column for column in LABEL_COLUMNS if column.startswith("has_")]
    report_lines = [
        "# Phase 3A DailyMed Label Enrichment Summary",
        "",
        f"Generated: {_now()}",
        "",
        f"- Science-review candidates attempted: {len(attempted)}",
        f"- Candidates with DailyMed match: {len(matched)}",
        f"- Candidates without match: {len(attempted) - len(matched)}",
        f"- Candidates not yet attempted: {len(rows) - len(attempted)}",
        f"- Shortlist rows exported: {len(shortlisted)}",
        "",
        "## Label match quality",
        "",
    ]
    report_lines.extend(
        f"- {quality}: {count}" for quality, count in sorted(quality_counts.items())
    )
    report_lines.extend(["", "## Burden signal counts", ""])
    report_lines.extend(
        f"- {column}: {sum(int(row[column] or 0) for row in matched)}"
        for column in flag_columns
    )
    report_lines.extend(
        [
            "",
            "## Top 30 scientific rescue signals",
            "",
            "| Ingredient | Signal score | Match | Triage | Rationale |",
            "|---|---:|---|---|---|",
        ]
    )
    report_lines.extend(
        f"| {row['ingredient_name']} | {row['scientific_rescue_signal_score']} | "
        f"{row['label_match_quality']} | {row['triage_class']} | "
        f"{str(row['scientific_review_rationale']).replace('|', '/')} |"
        for row in shortlisted[:30]
    )
    if not shortlisted:
        report_lines.append("| _No candidates met the current threshold_ | — | — | — | — |")
    report_lines.extend(
        [
            "",
            "## Key limitations",
            "",
            "- DailyMed matching is ingredient-name based and may select a label for only "
            "one manufacturer, strength, route, or product presentation.",
            "- Cached no-match results represent search results at retrieval time, not proof "
            "that no relevant label exists.",
            "- Keyword signals identify label language; they do not establish causality, "
            "technical feasibility, clinical value, or commercial opportunity.",
            "- Candidates not yet downloaded receive a missing-evidence penalty and cannot "
            "enter the high-confidence shortlist.",
            "",
            "This output is for hypothesis generation, not scientific, clinical, "
            "regulatory, legal, or investment validation.",
            "",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return {
        "candidates": len(rows),
        "attempted": len(attempted),
        "matched": len(matched),
        "without_match": len(attempted) - len(matched),
        "shortlisted": len(shortlisted),
    }
