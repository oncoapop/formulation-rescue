"""Phase 3.2 rescueability ranking for the fixed top-100 review set."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .database import PROJECT_ROOT
from .scientific_review import DEFAULT_REVIEW_CSV

DEFAULT_RESCUEABILITY_CSV = (
    PROJECT_ROOT / "data" / "processed" / "top100_rescueability_review.csv"
)
DEFAULT_RESCUEABILITY_REPORT = (
    PROJECT_ROOT / "reports" / "top100_rescueability_review.md"
)
DEFAULT_QUEUES_REPORT = PROJECT_ROOT / "reports" / "review_queues_summary.md"

RESCUEABILITY_COLUMNS = (
    "active_ingredient_family",
    "review_queue",
    "true_cytotoxic_antineoplastic_flag",
    "oncology_biologic_or_adc_flag",
    "immunomodulator_warning_flag",
    "cytotoxic_context_only_flag",
    "biosimilar_or_branded_family_duplicate_flag",
    "family_representative_flag",
    "family_representative_ingredient",
    "family_representative_reason",
    "duplicate_independent_review_reason",
    "rescueability_score",
    "rescueability_tier",
    "primary_rescue_hypothesis_type",
    "dominant_reason_to_deprioritise",
    "recommended_review_order",
    "rescueability_notes",
)

SALT_SUFFIXES = {
    "HYDROCHLORIDE", "SODIUM", "POTASSIUM", "ACETATE", "MESYLATE",
    "SULFATE", "PHOSPHATE", "CITRATE", "DIPHOSPHATE", "BROMIDE",
}
BIOLOGIC_SUFFIXES = {
    "ABBS", "ARRX", "PVVR", "DKST", "QYYP", "STRF", "AXXQ", "DYYB",
    "AEEB", "AAZG", "AZBT", "IRMB", "CMKB", "GCPT", "DLLE", "HRII",
    "OYSK", "ZZXF", "ATGA", "NGPT", "CXDL", "NXKI",
}
TRUE_CYTOTOXICS = {
    "PACLITAXEL", "DOCETAXEL", "DOXORUBICIN", "DAUNORUBICIN", "IDARUBICIN",
    "CYTARABINE", "CISPLATIN", "CARBOPLATIN", "OXALIPLATIN", "BLEOMYCIN",
    "MITOMYCIN", "MELPHALAN", "TOPOTECAN", "ETOPOSIDE", "IFOSFAMIDE",
    "BENDAMUSTINE", "CARMUSTINE", "DACTINOMYCIN", "IRINOTECAN",
    "MITOXANTRONE", "PENTOSTATIN", "FLUDARABINE", "CLADRIBINE", "IXABEPILONE",
}
ONCOLOGY_BIOLOGICS = {
    "TRASTUZUMAB", "TRASTUZUMAB DERUXTECAN", "FAM TRASTUZUMAB DERUXTECAN",
    "RITUXIMAB", "BLINATUMOMAB", "TARLATAMAB", "CETUXIMAB", "PANITUMUMAB",
    "OBINUTUZUMAB", "ELOTUZUMAB", "MARGETUXIMAB", "ZANIDATAMAB",
    "CARFILZOMIB", "BORTEZOMIB", "IBRITUMOMAB TIUXETAN",
    "DENILEUKIN DIFTITOX", "LINVOSELTAMAB", "ALEMTUZUMAB",
}
IMMUNOMODULATORS = {
    "ABATACEPT", "BELATACEPT", "INFLIXIMAB", "TOCILIZUMAB", "ETANERCEPT",
    "VEDOLIZUMAB", "ECULIZUMAB", "BELIMUMAB", "SILTUXIMAB", "PEGLOTICASE",
    "LECANEMAB", "DONANEMAB", "CERTOLIZUMAB PEGOL", "GLATIRAMER",
    "AZATHIOPRINE",
}
ANTI_INFECTIVES = {
    "TELAVANCIN", "FOSCARNET", "GANCICLOVIR", "MICAFUNGIN", "TIGECYCLINE",
    "AMPHOTERICIN B", "ANIDULAFUNGIN", "CASPOFUNGIN", "CEFEPIME",
    "CEFTIZOXIME", "CEFTOBIPROLE MEDOCARIL", "DAPTOMYCIN", "ORITAVANCIN",
}
ACUTE_CARE = {
    "OLICERIDINE", "VECURONIUM", "METHOHEXITAL", "ZICONOTIDE",
    "UROKINASE",
}
SEVERE_A_BLOCKERS = {
    "RENAL FAILURE", "LIVER FAILURE", "HEPATOTOXICITY", "CARDIOTOXICITY",
    "ANAPHYLAXIS", "STEVENS-JOHNSON SYNDROME", "SJS", "TEN",
    "CARCINOGENICITY", "MUTAGENICITY", "TERATOGENICITY", "CYTOTOXIC",
    "CHEMOTHERAPY", "ANTINEOPLASTIC", "NEUTROPENIA", "MYELOSUPPRESSION",
    "NARROW THERAPEUTIC INDEX",
}
VALID_QUEUES = {
    "small_molecule_reformulation", "anti_infective_specialist",
    "oncology_specialist", "biologic_delivery_specialist",
    "immunology_biologic", "acute_care_or_anaesthesia",
    "deprioritise_or_false_positive",
}
TIER_ORDER = {
    "A_strong_near_term_review": 0,
    "B_plausible_literature_review": 1,
    "C_specialist_only_review": 2,
    "D_deprioritise": 3,
    "E_likely_false_positive": 4,
}


def normalize_ingredient_name(value: str) -> str:
    """Return a base active name for taxonomy checks, preserving meaningful words."""
    normalized = re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()
    words = normalized.split()
    while words and words[-1] in SALT_SUFFIXES:
        words.pop()
    if words and words[-1] in BIOLOGIC_SUFFIXES:
        words.pop()
    return " ".join(words)


def active_ingredient_family(value: str) -> str:
    base = normalize_ingredient_name(value)
    if "FAM TRASTUZUMAB DERUXTECAN" in base:
        return "TRASTUZUMAB DERUXTECAN"
    if "TRASTUZUMAB AND HYALURONIDASE" in base or base.startswith(
        "PERTUZUMAB TRASTUZUMAB AND HYALURONIDASE"
    ):
        return "TRASTUZUMAB"
    for family in ("TRASTUZUMAB", "RITUXIMAB", "INFLIXIMAB", "TOCILIZUMAB", "ECULIZUMAB"):
        if base == family or base.startswith(f"{family} "):
            return family
    return base


def _matches(base: str, taxonomy: set[str]) -> bool:
    return any(base == item or base.startswith(f"{item} ") for item in taxonomy)


def classify_identity(row: Mapping[str, object]) -> dict[str, object]:
    name = str(row.get("ingredient_name", ""))
    base = normalize_ingredient_name(name)
    family = active_ingredient_family(name)
    true_cytotoxic = _matches(base, TRUE_CYTOTOXICS)
    oncology_biologic = _matches(base, ONCOLOGY_BIOLOGICS)
    immunomodulator = _matches(base, IMMUNOMODULATORS)
    previous_oncology_signal = str(row.get("toxicity_signal_class", "")) == "oncology_cytotoxic"
    context_only = previous_oncology_signal and not true_cytotoxic and not oncology_biologic
    return {
        "active_ingredient_family": family,
        "true_cytotoxic_antineoplastic_flag": int(true_cytotoxic),
        "oncology_biologic_or_adc_flag": int(oncology_biologic),
        "immunomodulator_warning_flag": int(immunomodulator),
        "cytotoxic_context_only_flag": int(context_only),
    }


def _bool(row: Mapping[str, object], key: str) -> bool:
    return str(row.get(key, "")).strip().casefold() in {"1", "true", "yes"}


def _integer(row: Mapping[str, object], key: str) -> int:
    try:
        return int(float(str(row.get(key, "0") or "0")))
    except ValueError:
        return 0


def _term_blob(row: Mapping[str, object]) -> str:
    return " ".join(
        str(row.get(key, ""))
        for key in (
            "administration_burden_terms", "safety_burden_terms",
            "formulation_burden_terms", "dosing_frequency_terms",
            "half_life_or_pk_terms", "phase1_notes",
        )
    ).casefold()


def primary_hypothesis(row: Mapping[str, object]) -> str:
    blob = _term_blob(row)
    route = str(row.get("canonical_route_list", "")).casefold()
    if _bool(row, "true_cytotoxic_antineoplastic_flag") or _bool(row, "oncology_biologic_or_adc_flag"):
        return "specialist_oncology_formulation"
    if _matches(normalize_ingredient_name(str(row.get("ingredient_name", ""))), ANTI_INFECTIVES):
        return "anti_infective_formulation_or_delivery"
    if _matches(normalize_ingredient_name(str(row.get("ingredient_name", ""))), ACUTE_CARE):
        return "acute_care_administration_simplification"
    if str(row.get("triage_class", "")) == "biologic_or_peptide":
        return "biologic_delivery_improvement"
    if "reconstit" in blob or "dilution" in blob or "special preparation" in blob:
        return "ready_to_use_or_reconstitution_reduction"
    if "refriger" in blob or "storage" in blob or "stability" in blob:
        return "storage_or_stability_improvement"
    if "injection site" in blob or "local irritation" in blob or "extravasation" in blob:
        return "local_tolerability_improvement"
    if "infusion" in blob:
        return "infusion_burden_reduction"
    if _integer(row, "score_pk_dosing_burden") > 0:
        return "modified_release_or_pk_smoothing"
    if _integer(row, "score_pediatric_gap") > 0:
        return "paediatric_formulation_gap"
    if _bool(row, "parenteral_route_signal"):
        return "route_conversion"
    return "unclear"


def preliminary_rescueability_score(row: Mapping[str, object]) -> int:
    """Score fixability independently of the Phase 3.1 burden score."""
    score = 0
    score += 3 if _bool(row, "all_products_discontinued") else 2 if _bool(row, "mixed_active_discontinued") else 0
    score += min(3, _integer(row, "score_administration_burden"))
    score += min(3, _integer(row, "score_formulation_handling_burden"))
    score += min(2, _integer(row, "score_route_conversion_opportunity"))
    score += min(2, _integer(row, "score_pk_dosing_burden"))
    score += 1 if _integer(row, "score_pediatric_gap") else 0
    score += 2 if _integer(row, "score_label_evidence_confidence") >= 2 else -3
    sensitivity = str(row.get("toxicity_formulation_sensitivity", ""))
    score += {"likely": 3, "possible": 2, "unknown": 0, "conflicting": -2, "unlikely": -3}.get(sensitivity, 0)
    score += 2 if str(row.get("triage_class", "")) != "biologic_or_peptide" else -2
    if _bool(row, "true_cytotoxic_antineoplastic_flag"):
        score -= 7
    if _bool(row, "oncology_biologic_or_adc_flag"):
        score -= 6
    concern = str(row.get("dominant_toxicity_concern", "")).upper()
    if concern in {"RENAL FAILURE", "LIVER FAILURE", "HEPATOTOXICITY", "CARDIOTOXICITY"}:
        score -= 5
    if sensitivity == "conflicting" and concern in SEVERE_A_BLOCKERS:
        score -= 4
    if _bool(row, "cytotoxic_context_only_flag"):
        score -= 2
    if not any(
        _integer(row, key)
        for key in (
            "score_administration_burden", "score_formulation_handling_burden",
            "score_route_conversion_opportunity", "score_pk_dosing_burden",
            "score_pediatric_gap",
        )
    ):
        score -= 4
    return max(0, score)


def select_family_representatives(
    rows: list[dict[str, object]],
) -> dict[str, tuple[str, str]]:
    """Select representatives without alphabetically pre-sorting score fallbacks."""
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[str(row["active_ingredient_family"])].append(row)
    selected = {}
    for family, members in groups.items():
        unsuffixed = [
            row for row in members
            if normalize_ingredient_name(str(row["ingredient_name"])) == family
            and str(row["ingredient_name"]).upper().replace("-", " ") == family
        ]
        if unsuffixed:
            representative = sorted(unsuffixed, key=lambda row: str(row["ingredient_name"]))[0]
            reason = "unsuffixed/reference core ingredient preferred"
        else:
            representative = max(
                members,
                key=lambda row: (
                    _integer(row, "rescueability_score"),
                    _integer(row, "score_formulation_handling_burden"),
                    _integer(row, "score_administration_burden"),
                    _integer(row, "scientific_rescue_signal_score"),
                    tuple(-ord(char) for char in str(row["ingredient_name"])),
                ),
            )
            reason = (
                "highest rescueability score; ties resolved by formulation burden, "
                "administration burden, scientific signal score, then ingredient name"
            )
        selected[family] = (str(representative["ingredient_name"]), reason)
    return selected


def _independent_duplicate_reason(
    row: Mapping[str, object], representative: Mapping[str, object]
) -> str:
    name = str(row.get("ingredient_name", "")).upper()
    if "HYALURONIDASE" in name:
        return "distinct hyaluronidase coformulation and product-presentation context"
    row_routes = {
        route for route in str(row.get("canonical_route_list", "")).split("; ")
        if route and route != "injectable"
    }
    rep_routes = {
        route for route in str(representative.get("canonical_route_list", "")).split("; ")
        if route and route != "injectable"
    }
    if row_routes and rep_routes and row_routes != rep_routes:
        return (
            f"distinct recorded route profile ({row.get('canonical_route_list')}) versus "
            f"representative ({representative.get('canonical_route_list')})"
        )
    row_forms = {
        form for form in str(row.get("canonical_dosage_form_list", "")).split("; ")
        if form and form != "injectable"
    }
    rep_forms = {
        form for form in str(representative.get("canonical_dosage_form_list", "")).split("; ")
        if form and form != "injectable"
    }
    if row_forms and rep_forms and row_forms != rep_forms:
        return (
            f"distinct recorded dosage-form profile ({row.get('canonical_dosage_form_list')})"
        )
    if _bool(row, "all_products_discontinued") != _bool(representative, "all_products_discontinued"):
        return "distinct discontinuation status"
    return ""


def assign_review_queue(row: Mapping[str, object]) -> str:
    if _bool(row, "biosimilar_or_branded_family_duplicate_flag") and not str(
        row.get("duplicate_independent_review_reason", "")
    ):
        return "deprioritise_or_false_positive"
    base = normalize_ingredient_name(str(row.get("ingredient_name", "")))
    if _bool(row, "true_cytotoxic_antineoplastic_flag") or _bool(row, "oncology_biologic_or_adc_flag"):
        return "oncology_specialist"
    if _matches(base, ANTI_INFECTIVES):
        return "anti_infective_specialist"
    if _bool(row, "immunomodulator_warning_flag"):
        return "immunology_biologic"
    if _matches(base, ACUTE_CARE):
        return "acute_care_or_anaesthesia"
    if str(row.get("triage_class", "")) == "biologic_or_peptide":
        return "biologic_delivery_specialist"
    if _bool(row, "cytotoxic_context_only_flag"):
        return "deprioritise_or_false_positive"
    return "small_molecule_reformulation"


def _severe_conflict(row: Mapping[str, object]) -> bool:
    return (
        str(row.get("toxicity_formulation_sensitivity", "")) == "conflicting"
        and str(row.get("dominant_toxicity_concern", "")).upper() in SEVERE_A_BLOCKERS
    )


def assign_tier(row: Mapping[str, object]) -> str:
    score = _integer(row, "rescueability_score")
    duplicate = _bool(row, "biosimilar_or_branded_family_duplicate_flag")
    independent = bool(str(row.get("duplicate_independent_review_reason", "")))
    queue = str(row.get("review_queue", ""))
    specialist = (
        _bool(row, "true_cytotoxic_antineoplastic_flag")
        or _bool(row, "oncology_biologic_or_adc_flag")
        or "narrow_therapeutic_index" in str(row.get("specialist_review_flags", ""))
        or queue in {"oncology_specialist", "biologic_delivery_specialist", "immunology_biologic"}
    )
    if duplicate and not independent:
        return "D_deprioritise"
    if (
        _bool(row, "cytotoxic_context_only_flag")
        and queue == "deprioritise_or_false_positive"
    ):
        return "D_deprioritise" if score >= 9 else "E_likely_false_positive"
    if specialist:
        return "C_specialist_only_review"
    if _severe_conflict(row):
        return "D_deprioritise" if score < 10 else "B_plausible_literature_review"
    if queue == "anti_infective_specialist":
        return "B_plausible_literature_review" if score >= 8 else "C_specialist_only_review"
    if (
        score >= 16
        and not duplicate
        and str(row.get("toxicity_formulation_sensitivity", "")) in {"likely", "possible"}
    ):
        return "A_strong_near_term_review"
    if score >= 9:
        return "B_plausible_literature_review"
    return "D_deprioritise"


def _deprioritise_reason(row: Mapping[str, object]) -> str:
    if _bool(row, "biosimilar_or_branded_family_duplicate_flag") and not row.get(
        "duplicate_independent_review_reason"
    ):
        return "non-representative family duplicate without distinct formulation rationale"
    if _bool(row, "cytotoxic_context_only_flag") and row.get("review_queue") == "deprioritise_or_false_positive":
        return "prior oncology/cytotoxic label classification appears contextual rather than active-identity based"
    if _bool(row, "true_cytotoxic_antineoplastic_flag"):
        return "intrinsic cytotoxic oncology mechanism requires specialist-only review"
    if _bool(row, "oncology_biologic_or_adc_flag"):
        return "oncology biologic/ADC complexity limits general formulation-rescue inference"
    if _severe_conflict(row):
        return "formulation-sensitive burden is overlapped by severe unresolved intrinsic toxicity"
    if str(row.get("triage_class", "")) == "biologic_or_peptide":
        return "biologic development and delivery require specialist feasibility review"
    if _integer(row, "rescueability_score") < 9:
        return "no sufficiently clear burden-to-formulation-fix link in current evidence"
    return ""


def _notes(row: Mapping[str, object]) -> str:
    reasons = [
        f"Distinct rescueability score based on status, administration/handling, route, PK, evidence quality, identity taxonomy, and toxicity conflict.",
        f"Primary hypothesis: {row.get('primary_rescue_hypothesis_type')}.",
    ]
    if _bool(row, "cytotoxic_context_only_flag"):
        reasons.append(
            "Phase 3.1 oncology language is treated as contextual because active-identity taxonomy does not support a cytotoxic/oncology classification."
        )
    if _bool(row, "biosimilar_or_branded_family_duplicate_flag"):
        reasons.append(
            f"Family duplicate of {row.get('family_representative_ingredient')}; "
            f"independent rationale: {row.get('duplicate_independent_review_reason') or 'none identified'}."
        )
    if _severe_conflict(row):
        reasons.append("Severe conflict blocks A-tier assignment.")
    reasons.append(
        "This rule-based rank does not establish clinical utility, technical feasibility, regulatory eligibility, patent freedom, or commercial viability."
    )
    return " ".join(reasons)


def build_rescueability_review(
    input_path: Path = DEFAULT_REVIEW_CSV,
    output_path: Path = DEFAULT_RESCUEABILITY_CSV,
    report_path: Path = DEFAULT_RESCUEABILITY_REPORT,
    queues_report_path: Path = DEFAULT_QUEUES_REPORT,
) -> list[dict[str, object]]:
    with input_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        original_columns = list(reader.fieldnames or [])
        source_rows = list(reader)
    if len(source_rows) != 100:
        raise ValueError(f"Expected fixed top-100 input; found {len(source_rows)} rows")
    rows: list[dict[str, object]] = []
    for source in source_rows:
        row = {**source, **classify_identity(source)}
        row["primary_rescue_hypothesis_type"] = primary_hypothesis(row)
        row["rescueability_score"] = preliminary_rescueability_score(row)
        rows.append(row)

    representatives = select_family_representatives(rows)
    by_name = {str(row["ingredient_name"]): row for row in rows}
    for row in rows:
        representative_name, reason = representatives[str(row["active_ingredient_family"])]
        is_representative = str(row["ingredient_name"]) == representative_name
        row["family_representative_flag"] = int(is_representative)
        row["family_representative_ingredient"] = representative_name
        row["family_representative_reason"] = reason
        row["biosimilar_or_branded_family_duplicate_flag"] = int(not is_representative)
        row["duplicate_independent_review_reason"] = (
            "" if is_representative
            else _independent_duplicate_reason(row, by_name[representative_name])
        )
        if is_representative:
            row["rescueability_score"] = _integer(row, "rescueability_score") + 1
        elif not row["duplicate_independent_review_reason"]:
            row["rescueability_score"] = max(
                0, _integer(row, "rescueability_score") - 5
            )
        row["review_queue"] = assign_review_queue(row)
        row["rescueability_tier"] = assign_tier(row)
        row["dominant_reason_to_deprioritise"] = _deprioritise_reason(row)
        row["rescueability_notes"] = _notes(row)

    ordered = sorted(
        rows,
        key=lambda row: (
            TIER_ORDER[str(row["rescueability_tier"])],
            _bool(row, "biosimilar_or_branded_family_duplicate_flag")
            and not bool(row["duplicate_independent_review_reason"]),
            -_integer(row, "rescueability_score"),
            -_integer(row, "scientific_rescue_signal_score"),
            str(row["ingredient_name"]),
        ),
    )
    for order, row in enumerate(ordered, start=1):
        row["recommended_review_order"] = order
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=original_columns + list(RESCUEABILITY_COLUMNS),
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
    _write_main_report(rows, report_path)
    _write_queues_report(rows, queues_report_path)
    return rows


def _count_lines(rows: Iterable[Mapping[str, object]], key: str) -> list[str]:
    counts = Counter(str(row.get(key, "")) for row in rows)
    return [f"- {name or '(blank)'}: {count}" for name, count in sorted(counts.items())]


def _table_rows(rows: Iterable[Mapping[str, object]]) -> list[str]:
    return [
        f"| {row['recommended_review_order']} | {row['ingredient_name']} | "
        f"{row['rescueability_score']} | {row['scientific_rescue_signal_score']} | "
        f"{row['rescueability_tier']} | {row['review_queue']} | "
        f"{row['primary_rescue_hypothesis_type']} | "
        f"{str(row['rescueability_notes']).replace('|', '/')} |"
        for row in rows
    ]


def _write_main_report(rows: list[dict[str, object]], path: Path) -> None:
    ordered = sorted(rows, key=lambda row: _integer(row, "recommended_review_order"))
    by_rescueability = sorted(
        rows,
        key=lambda row: (
            -_integer(row, "rescueability_score"),
            -_integer(row, "scientific_rescue_signal_score"),
            str(row["ingredient_name"]),
        ),
    )
    families: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        families[str(row["active_ingredient_family"])].append(row)
    duplicate_families = {
        family: members for family, members in families.items() if len(members) > 1
    }
    false_positives = [
        row for row in ordered
        if row["rescueability_tier"] == "E_likely_false_positive"
        or row["review_queue"] == "deprioritise_or_false_positive"
    ]
    lines = [
        "# Top-100 Rescueability Review",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Purpose",
        "",
        "Phase 3.2 separates label/product burden from plausible formulation rescueability. "
        "The Phase 3.1 scientific rescue signal score ranks how loudly burden appears; the "
        "new rescueability score independently estimates whether current evidence links that "
        "burden to a potentially modifiable route, formulation, handling, dosing, exposure, "
        "storage, device, or presentation issue.",
        "",
        "This is deterministic hypothesis generation, not scientific, clinical, formulation, "
        "regulatory, patent, commercial, or investment validation.",
        "",
        "## Review queue definitions",
        "",
        "- small_molecule_reformulation: non-biologic therapeutics with a plausible general formulation question.",
        "- anti_infective_specialist: products requiring resistance, stewardship, infection, or hospital-use context.",
        "- oncology_specialist: classical cytotoxics and oncology biologics/ADCs or specialist agents.",
        "- biologic_delivery_specialist: complex proteins, enzymes, peptides, or toxins with biologic-specific delivery questions.",
        "- immunology_biologic: immunomodulators whose warnings must not be mistaken for intrinsic cytotoxic identity.",
        "- acute_care_or_anaesthesia: ICU, emergency, anaesthesia, paralytic, intrathecal, or acute-administration products.",
        "- deprioritise_or_false_positive: weak links, contextual cytotoxic language, or duplicate family members without an independent rationale.",
        "",
        "## Rescueability tiers",
        "",
        "- A_strong_near_term_review: strongest non-conflicted, non-duplicate candidates for immediate manual review.",
        "- B_plausible_literature_review: plausible burden-to-fix link with unresolved evidence.",
        "- C_specialist_only_review: oncology, biologic, NTI, or other specialist feasibility/safety context.",
        "- D_deprioritise: weak, crowded, duplicate, or severely conflicted rationale.",
        "- E_likely_false_positive: active-identity correction suggests the prior loud signal is unrelated to formulation rescue.",
        "",
        "## Counts by review queue",
        "",
        *_count_lines(rows, "review_queue"),
        "",
        "## Counts by rescueability tier",
        "",
        *_count_lines(rows, "rescueability_tier"),
        "",
        "## Identity correction counts",
        "",
        f"- true_cytotoxic_antineoplastic_flag: {sum(_bool(row, 'true_cytotoxic_antineoplastic_flag') for row in rows)}",
        f"- oncology_biologic_or_adc_flag: {sum(_bool(row, 'oncology_biologic_or_adc_flag') for row in rows)}",
        f"- immunomodulator_warning_flag: {sum(_bool(row, 'immunomodulator_warning_flag') for row in rows)}",
        f"- cytotoxic_context_only_flag: {sum(_bool(row, 'cytotoxic_context_only_flag') for row in rows)}",
        f"- duplicate family clusters: {len(duplicate_families)}",
        "",
        "## Top 20 by rescueability score",
        "",
        "| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |",
        "|---:|---|---:|---:|---|---|---|---|",
        *_table_rows(by_rescueability[:20]),
        "",
        "## Top candidates per review queue",
        "",
    ]
    for queue in sorted(VALID_QUEUES):
        queue_rows = [row for row in ordered if row["review_queue"] == queue][:5]
        lines += [
            f"### {queue}",
            "",
            "| Order | Ingredient | Rescueability | Burden score | Tier | Queue | Primary hypothesis | Notes |",
            "|---:|---|---:|---:|---|---|---|---|",
            *_table_rows(queue_rows),
            "",
        ]
        if not queue_rows:
            lines.append("_No candidates assigned._\n")
    lines += [
        "## Likely false positives",
        "",
        "| Ingredient | Prior signal | Corrected reason |",
        "|---|---|---|",
    ]
    lines += [
        f"| {row['ingredient_name']} | {row['toxicity_signal_class']} / "
        f"{row['dominant_toxicity_concern']} | {row['dominant_reason_to_deprioritise']} |"
        for row in false_positives
    ] or ["| _None under current rules_ | — | — |"]
    lines += ["", "## Duplicate family clusters and representatives", ""]
    if duplicate_families:
        lines += [
            "| Family | Members | Representative | Selection reason |",
            "|---|---|---|---|",
        ]
        for family, members in sorted(duplicate_families.items()):
            lines.append(
                f"| {family} | {'; '.join(str(row['ingredient_name']) for row in members)} | "
                f"{members[0]['family_representative_ingredient']} | "
                f"{members[0]['family_representative_reason']} |"
            )
    else:
        lines.append("_No duplicate family clusters detected._")
    lines += [
        "",
        "## Limitations",
        "",
        "- Taxonomy is a transparent curated screening list, not a complete pharmacologic ontology.",
        "- Scores encode review heuristics and deliberately avoid probability or feasibility claims.",
        "- Current product records cannot establish whether an apparent gap has already been solved by a marketed alternative.",
        "- DailyMed matches and keyword burdens may be presentation-specific or context-only.",
        "- Discontinuation cause, shortage, clinical relevance, PK/PD causality, comparator landscape, formulation feasibility, patent/FTO, and regulatory pathway remain unvalidated.",
        "",
        "## Recommended next manual review workflow",
        "",
        "1. Review A-tier representatives for a concrete burden-to-formulation-fix link and current comparator landscape.",
        "2. Review B-tier representatives with targeted literature, label, PK/PD, discontinuation, and formulation-feasibility questions.",
        "3. Route C-tier representatives to the queue-specific subject-matter expert before general prioritisation.",
        "4. Review independent duplicate rationales; otherwise use the selected family representative.",
        "5. Confirm E-tier identity/context corrections manually before rejecting any candidate.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


QUEUE_GUIDANCE = {
    "small_molecule_reformulation": (
        "Validate the specific route, handling, stability, local-tolerability, or PK hypothesis against current products and literature.",
        "Formulation scientist with clinical pharmacology input",
    ),
    "anti_infective_specialist": (
        "Assess stewardship, resistance, treatment setting, infusion constraints, and whether delivery changes preserve exposure targets.",
        "Infectious-disease pharmacologist or anti-infective clinician",
    ),
    "oncology_specialist": (
        "Separate intrinsic antitumour toxicity from excipient, infusion, route, exposure, and handling burden before considering feasibility.",
        "Oncology pharmacist/clinician plus oncology formulation and regulatory specialists",
    ),
    "biologic_delivery_specialist": (
        "Assess protein stability, immunogenicity, concentration, device, route, and biologic regulatory constraints.",
        "Biologics formulation and delivery specialist",
    ),
    "immunology_biologic": (
        "Review immune mechanism, infection/malignancy warnings, immunogenicity, delivery, and family crowding.",
        "Immunology/rheumatology specialist plus biologics formulation expert",
    ),
    "acute_care_or_anaesthesia": (
        "Assess workflow, onset/offset, titration, compatibility, preparation, device, and medication-error burden.",
        "Critical-care or anaesthesia pharmacist/clinician",
    ),
    "deprioritise_or_false_positive": (
        "Confirm identity/context correction and inspect only if a distinct product-presentation or discontinuation rationale emerges.",
        "General scientific reviewer; escalate only if new evidence supports a specific hypothesis",
    ),
}


def _write_queues_report(rows: list[dict[str, object]], path: Path) -> None:
    ordered = sorted(rows, key=lambda row: _integer(row, "recommended_review_order"))
    lines = [
        "# Phase 3.2 Review Queues Summary",
        "",
        "These queues route hypotheses to appropriate manual review; they do not validate development opportunities.",
        "",
    ]
    for queue in (
        "small_molecule_reformulation", "anti_infective_specialist",
        "oncology_specialist", "biologic_delivery_specialist",
        "immunology_biologic", "acute_care_or_anaesthesia",
        "deprioritise_or_false_positive",
    ):
        action, expert = QUEUE_GUIDANCE[queue]
        queue_rows = [row for row in ordered if row["review_queue"] == queue]
        lines += [
            f"## {queue}",
            "",
            f"- Candidates: {len(queue_rows)}",
            f"- Recommended next action: {action}",
            f"- Suggested subject-matter expert: {expert}",
            "",
            "| Order | Ingredient | Score | Tier | Family status | Primary hypothesis |",
            "|---:|---|---:|---|---|---|",
        ]
        for row in queue_rows[:10]:
            family_status = (
                "representative"
                if _bool(row, "family_representative_flag")
                else f"duplicate of {row['family_representative_ingredient']}"
            )
            lines.append(
                f"| {row['recommended_review_order']} | {row['ingredient_name']} | "
                f"{row['rescueability_score']} | {row['rescueability_tier']} | "
                f"{family_status} | {row['primary_rescue_hypothesis_type']} |"
            )
        if not queue_rows:
            lines.append("| — | _No candidates assigned_ | — | — | — | — |")
        lines.append("")
    lines += [
        "## Interpretation limitation",
        "",
        "Queue assignment and order are deterministic screening aids. They do not establish "
        "clinical utility, technical feasibility, regulatory eligibility, patent freedom, "
        "commercial viability, or a validated formulation-rescue opportunity.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
