"""Offline Phase 3.1 interpretation of the fixed top-100 review set."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .database import PROJECT_ROOT
from .dailymed import DEFAULT_DAILYMED_RAW, DEFAULT_SIGNALS_CSV, xml_label_text

DEFAULT_REVIEW_CSV = (
    PROJECT_ROOT / "data" / "processed" / "top_scientific_rescue_signals_review.csv"
)
DEFAULT_REVIEW_REPORT = PROJECT_ROOT / "reports" / "top100_scientific_review.md"

BASE_REVIEW_COLUMNS = (
    "rank",
    "ingredient_name",
    "triage_class",
    "triage_subclass",
    "science_review_priority",
    "scientific_rescue_signal_score",
    "product_count",
    "active_product_count",
    "discontinued_product_count",
    "all_products_discontinued",
    "mixed_active_discontinued",
    "canonical_route_list",
    "canonical_dosage_form_list",
    "parenteral_route_signal",
    "score_administration_burden",
    "score_safety_burden",
    "score_formulation_handling_burden",
    "score_pediatric_gap",
    "score_route_conversion_opportunity",
    "score_label_evidence_confidence",
    "label_match_quality",
    "administration_burden_terms",
    "safety_burden_terms",
    "formulation_burden_terms",
    "phase1_notes",
    "evidence_completeness_notes",
)

INTERPRETATION_COLUMNS = (
    "toxicity_signal_class",
    "toxicity_formulation_sensitivity",
    "toxicity_mechanism_notes",
    "toxicity_review_priority",
    "has_conflicting_toxicity_signals",
    "dominant_toxicity_concern",
    "formulation_rescue_optimism_penalty",
    "manual_safety_review_required",
    "toxicity_conflict_notes",
    "dosing_frequency_terms",
    "half_life_or_pk_terms",
    "pk_terms_detected",
    "pk_context_quality",
    "pk_parent_metabolite_ambiguous",
    "pk_population_context",
    "pk_review_required",
    "score_pk_dosing_burden",
    "specialist_review_flags",
    "potential_regulatory_pathway",
    "regulatory_pathway_confidence",
    "regulatory_notes",
    "main_detected_burden",
    "candidate_hypothesis",
    "suggested_manual_disposition",
    "manual_disposition",
    "next_evidence_needed",
    "reviewer_notes",
)

REVIEW_COLUMNS = BASE_REVIEW_COLUMNS + INTERPRETATION_COLUMNS

LOCAL_PATTERNS = {
    "injection site reaction": r"\binjection[ -]site reaction",
    "injection site pain": r"\binjection[ -]site pain",
    "injection site erythema": r"\binjection[ -]site erythema",
    "injection site swelling": r"\binjection[ -]site swelling",
    "local irritation": r"\blocal irritation",
    "extravasation": r"\bextravasation",
}
INFUSION_PATTERNS = {
    "administration-related reaction": r"\badministration[ -]related reaction",
    "infusion reaction": r"\binfusion reaction",
    "infusion-related reaction": r"\binfusion[ -]related reaction",
    "infusion site reaction": r"\binfusion[ -]site reaction",
}
EXPOSURE_PATTERNS = {
    "Cmax": r"\bcmax\b",
    "peak concentration": r"\bpeak concentration",
    "peak plasma concentration": r"\bpeak plasma concentration",
    "rapid absorption": r"\brapid absorption",
    "dose-related adverse reaction": r"\bdose[ -]related adverse reaction",
    "concentration-related": r"\bconcentration[ -]related",
    "exposure-related": r"\bexposure[ -]related",
    "hypotension after administration": r"\bhypotension.{0,45}after administration",
    "sedation after dosing": r"\bsedation.{0,45}after dos",
}
SYSTEMIC_PATTERNS = {
    "nausea": r"\bnausea\b",
    "vomiting": r"\bvomiting\b",
    "dizziness": r"\bdizziness\b",
    "hypotension": r"\bhypotension\b",
    "QT prolongation": r"\bqt prolongation",
    "renal impairment": r"\brenal impairment",
    "renal toxicity": r"\brenal toxicity",
    "nephrotoxicity": r"\bnephrotox",
}
ORGAN_PATTERNS = {
    "hepatotoxicity": r"\bhepatotox",
    "liver failure": r"\bliver failure",
    "severe liver injury": r"\bsevere liver injury",
    "renal failure": r"\brenal failure",
    "cardiotoxicity": r"\bcardiotox",
    "irreversible organ toxicity": r"\birreversible organ toxicity",
}
REPRODUCTIVE_PATTERNS = {
    "carcinogenicity": r"\bcarcinogenic",
    "mutagenicity": r"\bmutagen",
    "teratogenicity": r"\bteratogen",
    "embryo-fetal toxicity": r"\bembryo[ -]fetal toxicity",
}
SEVERE_IMMUNE_PATTERNS = {
    "Stevens-Johnson syndrome": r"\bstevens[ -]johnson syndrome|\bsjs\b",
    # Do not match bare "TEN": ordinary prose commonly contains the word "ten".
    "toxic epidermal necrolysis": r"\btoxic epidermal necrolysis",
    "anaphylaxis": r"\banaphyla",
    "severe hypersensitivity": r"\bsevere hypersensitiv",
}
IMMUNE_PATTERNS = {
    "hypersensitivity": r"\bhypersensitiv",
    "anaphylaxis": r"\banaphyla",
    "immunogenicity": r"\bimmunogenic",
    "antibody formation": r"\bantibody formation",
    "anti-drug antibodies": r"\banti[ -]drug antibod",
}
ONCOLOGY_PATTERNS = {
    "antineoplastic": r"\bantineoplastic",
    "cytotoxic": r"\bcytotoxic",
    "chemotherapy": r"\bchemotherap",
    "myelosuppression": r"\bmyelosuppress",
    "neutropenia": r"\bneutropenia",
    "thrombocytopenia": r"\bthrombocytopenia",
    "severe marrow suppression": r"\bsevere marrow suppression",
    "bone marrow suppression": r"\bbone marrow suppression",
    "febrile neutropenia": r"\bfebrile neutropenia",
}
NTI_PATTERNS = {
    "narrow therapeutic index": r"\bnarrow therapeutic index",
    "therapeutic drug monitoring": r"\btherapeutic drug monitoring",
    "serum concentration monitoring": r"\bserum concentration monitoring",
    "plasma concentration monitoring": r"\bplasma concentration monitoring",
    "toxicity monitoring": r"\btoxicity monitoring",
    "dose titration to serum level": r"\bdose titration.{0,30}serum level",
}
DOSING_PATTERNS = {
    "once daily": r"\bonce daily\b",
    "twice daily": r"\btwice daily\b",
    "three times daily": r"\bthree times daily\b",
    "four times daily": r"\bfour times daily\b",
    "every 4 hours": r"\bevery 4 hours\b",
    "every 6 hours": r"\bevery 6 hours\b",
    "every 8 hours": r"\bevery 8 hours\b",
    "every 12 hours": r"\bevery 12 hours\b",
    "every 24 hours": r"\bevery 24 hours\b",
    "continuous infusion": r"\bcontinuous infusion\b",
    "dose titration": r"\bdose titration\b",
    "titrate": r"\btitrat",
    "missed dose": r"\bmissed dose\b",
    "steady state": r"\bsteady state\b",
}
PK_PATTERNS = {
    "terminal half-life": r"\bterminal half[ -]life\b",
    "elimination half-life": r"\belimination half[ -]life\b",
    "half-life": r"\bhalf[ -]life\b",
    "Cmax": r"\bcmax\b",
    "AUC": r"\bauc\b",
    "peak plasma concentration": r"\bpeak plasma concentration\b",
    "peak concentration": r"\bpeak concentration\b",
    "steady state": r"\bsteady state\b",
    "clearance": r"\bclearance\b",
    "volume of distribution": r"\bvolume of distribution\b",
    "active metabolite": r"\bactive metabolite\b",
    "metabolite": r"\bmetabolite",
}


def _terms(text: str, patterns: Mapping[str, str]) -> list[str]:
    return [name for name, pattern in patterns.items() if re.search(pattern, text, re.I)]


def _joined(values: list[str]) -> str:
    return "; ".join(dict.fromkeys(values))


def _truth(value: object) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes"}


def _near_pk_population(text: str) -> list[str]:
    populations = {
        "renal impairment": r"\brenal impairment\b",
        "hepatic impairment": r"\bhepatic impairment\b",
        "paediatric": r"\b(?:paediatric|pediatric)\b",
        "geriatric": r"\bgeriatric\b",
        "pregnancy": r"\bpregnan",
    }
    pk_anchor = r"(?:half[ -]life|cmax|auc|peak concentration|clearance|metabolite)"
    found = []
    for name, pattern in populations.items():
        if re.search(f"(?:{pk_anchor}).{{0,300}}(?:{pattern})|(?:{pattern}).{{0,300}}(?:{pk_anchor})", text, re.I):
            found.append(name)
    return found


def interpret_scientific_signals(
    row: Mapping[str, object], label_text: str
) -> dict[str, object]:
    """Interpret one candidate using label text as screening evidence."""
    text = " ".join(label_text.split())
    local = _terms(text, LOCAL_PATTERNS)
    infusion = _terms(text, INFUSION_PATTERNS)
    exposure = _terms(text, EXPOSURE_PATTERNS)
    systemic = _terms(text, SYSTEMIC_PATTERNS)
    organ = _terms(text, ORGAN_PATTERNS)
    reproductive = _terms(text, REPRODUCTIVE_PATTERNS)
    severe_immune = _terms(text, SEVERE_IMMUNE_PATTERNS)
    immune = _terms(text, IMMUNE_PATTERNS)
    oncology = _terms(text, ONCOLOGY_PATTERNS)
    nti = _terms(text, NTI_PATTERNS)
    dosing = _terms(text, DOSING_PATTERNS)
    pk = _terms(text, PK_PATTERNS)

    triage = str(row.get("triage_class", ""))
    subclass = str(row.get("triage_subclass", ""))
    triage_blob = f"{triage} {subclass}".casefold()
    specialist = []
    major_oncology = bool(
        set(oncology)
        & {
            "antineoplastic",
            "cytotoxic",
            "myelosuppression",
            "severe marrow suppression",
            "bone marrow suppression",
            "febrile neutropenia",
        }
    ) or len(oncology) >= 2
    if major_oncology:
        specialist.append("oncology_cytotoxic")
    if nti:
        specialist.append("narrow_therapeutic_index")
    for flag in (
        "controlled_substance_or_abuse_risk",
        "obsolete_antibiotic",
        "radiopharmaceutical",
        "diagnostic_agent",
        "contrast_agent",
        "biologic_or_peptide",
    ):
        if flag in triage_blob:
            specialist.append(flag)

    formulation_signal = bool(local or infusion)
    intrinsic_signal = bool(organ or reproductive or severe_immune or major_oncology or nti)
    conflict = formulation_signal and intrinsic_signal

    if major_oncology:
        signal_class, dominant = "oncology_cytotoxic", oncology[0]
    elif organ:
        signal_class, dominant = "organ_toxicity", organ[0]
    elif severe_immune:
        signal_class, dominant = "immunogenicity", severe_immune[0]
    elif reproductive:
        signal_class, dominant = "reproductive_genotoxicity", reproductive[0]
    elif nti:
        signal_class, dominant = "narrow_therapeutic_index", nti[0]
    elif exposure:
        signal_class, dominant = "exposure_peak_possible", exposure[0]
    elif infusion:
        signal_class, dominant = "infusion_related", infusion[0]
    elif local:
        signal_class, dominant = "route_local", local[0]
    elif immune:
        signal_class, dominant = "immunogenicity", immune[0]
    elif systemic:
        signal_class, dominant = "systemic_intrinsic_possible", systemic[0]
    else:
        signal_class, dominant = "unknown", "unknown"

    if conflict:
        sensitivity = "conflicting"
    elif organ or reproductive or severe_immune or major_oncology or nti:
        sensitivity = "possible" if exposure else "unlikely"
    elif exposure or infusion or immune:
        sensitivity = "possible"
    elif local:
        sensitivity = "likely"
    elif systemic:
        sensitivity = "possible" if exposure else "unknown"
    else:
        sensitivity = "unknown"

    manual_safety = intrinsic_signal or conflict
    review_priority = (
        "high" if manual_safety or severe_immune else "medium"
        if signal_class != "unknown" else "low"
    )
    penalty = 3 if conflict else 2 if intrinsic_signal else 0
    conflict_notes = ""
    if conflict:
        conflict_notes = (
            f"Formulation-sensitive signal ({_joined(local + infusion)}) overlaps "
            f"with higher-priority intrinsic/specialist concern ({dominant}); "
            "route burden must not be treated as evidence that intrinsic toxicity is rescueable."
        )

    population = _near_pk_population(text)
    metabolite_ambiguous = bool(
        pk
        and _terms(text, {"metabolite": PK_PATTERNS["metabolite"]})
        and _terms(text, {"kinetic term": r"\b(?:half[ -]life|cmax|auc|clearance)\b"})
    )
    if not pk:
        pk_quality = "none"
    elif len(pk) >= 3 and not metabolite_ambiguous:
        pk_quality = "medium"
    else:
        pk_quality = "low"
    pk_review = bool(pk and (pk_quality in {"low", "medium"} or metabolite_ambiguous or population))
    frequent = any(
        term in dosing
        for term in ("three times daily", "four times daily", "every 4 hours", "every 6 hours", "every 8 hours")
    )
    schedule_burden = bool(
        frequent
        or "continuous infusion" in dosing
        or "dose titration" in dosing
        or "titrate" in dosing
    )
    pk_score = min(3, (2 if frequent else 1 if schedule_burden else 0) + (1 if pk and dosing else 0))

    label_quality = str(row.get("label_match_quality", ""))
    confidence_score = int(row.get("score_label_evidence_confidence") or 0)
    evidence_low = label_quality not in {"exact", "high"} or confidence_score < 2 or not text

    if specialist:
        disposition = "specialist_category"
    elif conflict or signal_class in {
        "organ_toxicity", "reproductive_genotoxicity", "immunogenicity",
        "exposure_peak_possible", "systemic_intrinsic_possible",
    } or pk_review:
        disposition = "literature_review"
    elif (
        not evidence_low
        and sensitivity in {"likely", "possible"}
        and formulation_signal
        and (int(row.get("score_formulation_handling_burden") or 0) >= 2)
    ):
        disposition = "advance"
    else:
        disposition = "deprioritise"

    if "biologic_or_peptide" in triage_blob:
        pathway = "biologic_pathway_review_needed"
        pathway_confidence = "medium"
        regulatory_notes = "Biologic status/pathway requires confirmation."
    elif specialist:
        pathway = "specialist_regulatory_review_needed"
        pathway_confidence = "high" if triage in specialist else "medium"
        regulatory_notes = "Specialist category requires product-specific pathway review."
    elif evidence_low:
        pathway = "unknown"
        pathway_confidence = "low"
        regulatory_notes = "Label or product evidence is insufficient for a pathway inference."
    elif triage == "therapeutic_drug" and _truth(row.get("parenteral_route_signal")) and (
        int(row.get("score_formulation_handling_burden") or 0) > 0 or formulation_signal
    ):
        if _truth(row.get("all_products_discontinued")):
            pathway = "likely_505b2_reformulation"
            pathway_confidence = "medium"
        else:
            pathway = "possible_505b2_route_or_form_change"
            pathway_confidence = "medium"
        regulatory_notes = "Screening inference based on route/form burden; product-specific 505(b)(2) review is required."
    elif triage == "therapeutic_drug":
        pathway = "generic_505j_or_low_differentiation"
        pathway_confidence = "low"
        regulatory_notes = "Only same-route or generic-like differentiation is apparent from current evidence."
    else:
        pathway = "unknown"
        pathway_confidence = "low"
        regulatory_notes = "No conservative pathway inference is supported."

    burden_scores = {
        "administration_burden": int(row.get("score_administration_burden") or 0),
        "formulation_handling_burden": int(row.get("score_formulation_handling_burden") or 0),
        "safety_tolerability_burden": int(row.get("score_safety_burden") or 0),
        "pediatric_gap": int(row.get("score_pediatric_gap") or 0),
        "pk_dosing_burden": pk_score,
        "specialist_safety_burden": 4 if specialist or intrinsic_signal else 0,
        "incomplete_evidence": 5 if evidence_low else 0,
    }
    main_burden = max(burden_scores, key=burden_scores.get)

    detected = local + infusion + exposure + organ + reproductive + severe_immune + oncology + nti
    term = detected[0] if detected else (
        str(row.get("formulation_burden_terms", "")).split(";")[0].strip()
        or str(row.get("administration_burden_terms", "")).split(";")[0].strip()
        or "limited label evidence"
    )
    status = (
        "all products discontinued" if _truth(row.get("all_products_discontinued"))
        else "mixed active/discontinued products" if _truth(row.get("mixed_active_discontinued"))
        else "active products recorded"
    )
    route = str(row.get("canonical_route_list", "") or "route not established")
    if conflict:
        hypothesis = (
            f"{row.get('ingredient_name')} needs specialist review: {term} occurs with "
            f"{dominant} in a {route} {triage.replace('_', ' ')} with {status}. "
            "Reformulation optimism should remain limited until intrinsic toxicity is separated "
            "from route, handling, excipient, or exposure-profile burden."
        )
    elif specialist:
        hypothesis = (
            f"{row.get('ingredient_name')} requires specialist review because {dominant} "
            f"was detected for a {route} {triage.replace('_', ' ')} with {status}. "
            f"Formulation sensitivity is {sensitivity}; any route, handling, dosing, or "
            "exposure-profile hypothesis must be assessed within the specialist safety "
            "and regulatory context."
        )
    elif pk_review and not formulation_signal:
        hypothesis = (
            f"{row.get('ingredient_name')} remains a literature-review case because "
            f"{_joined(pk[:2]) or 'PK terms'} and {_joined(dosing[:2]) or 'dosing context'} "
            f"were detected in a {route} product, but parent-drug, metabolite, and "
            "population-specific context is not established."
        )
    else:
        hypothesis = (
            f"{row.get('ingredient_name')} warrants {disposition.replace('_', ' ')} review as a "
            f"{route} {triage.replace('_', ' ')} with {status}; label evidence includes {term}. "
            f"Formulation sensitivity is {sensitivity} and should be tested against route, "
            "handling, excipient, exposure-profile, and intrinsic-mechanism explanations."
        )

    evidence_needed = []
    if formulation_signal:
        evidence_needed += ["formulation feasibility review", "comparator formulation landscape"]
    if exposure or systemic or pk_review:
        evidence_needed += ["PK/PD review", "exposure-toxicity literature"]
    if intrinsic_signal:
        evidence_needed += ["label/manual review"]
    if major_oncology:
        evidence_needed += ["specialist oncology review"]
    if nti:
        evidence_needed += ["NTI safety/regulatory review"]
    if _truth(row.get("all_products_discontinued")) or _truth(row.get("mixed_active_discontinued")):
        evidence_needed += ["discontinuation reason", "current clinical relevance"]
    if pathway != "unknown":
        evidence_needed += ["505(b)(2)/regulatory review", "patent/FTO review"]
    if evidence_low:
        evidence_needed += ["label/manual review"]

    mechanism_notes = (
        f"Detected: {_joined(detected + systemic + immune) or 'no specific toxicity language'}. "
        "Keyword evidence does not establish causality; assess intrinsic, target-mediated, "
        "metabolite-, exposure-, route-, excipient-, concentration-, and device-related mechanisms."
    )
    return {
        "toxicity_signal_class": signal_class,
        "toxicity_formulation_sensitivity": sensitivity,
        "toxicity_mechanism_notes": mechanism_notes,
        "toxicity_review_priority": review_priority,
        "has_conflicting_toxicity_signals": int(conflict),
        "dominant_toxicity_concern": dominant,
        "formulation_rescue_optimism_penalty": penalty,
        "manual_safety_review_required": int(manual_safety),
        "toxicity_conflict_notes": conflict_notes,
        "dosing_frequency_terms": _joined(dosing),
        "half_life_or_pk_terms": _joined(pk),
        "pk_terms_detected": int(bool(pk)),
        "pk_context_quality": pk_quality,
        "pk_parent_metabolite_ambiguous": int(metabolite_ambiguous),
        "pk_population_context": _joined(population) or "none detected",
        "pk_review_required": int(pk_review),
        "score_pk_dosing_burden": pk_score,
        "specialist_review_flags": _joined(specialist),
        "potential_regulatory_pathway": pathway,
        "regulatory_pathway_confidence": pathway_confidence,
        "regulatory_notes": regulatory_notes,
        "main_detected_burden": main_burden,
        "candidate_hypothesis": hypothesis,
        "suggested_manual_disposition": disposition,
        "manual_disposition": "",
        "next_evidence_needed": _joined(evidence_needed) or "current clinical relevance; label/manual review",
        "reviewer_notes": "",
    }


def _local_label_texts(raw_dir: Path, ingredients: set[str]) -> dict[str, str]:
    labels = {}
    if not raw_dir.exists():
        return labels
    for manifest_path in raw_dir.glob("*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") != "matched":
                continue
            ingredient = str(manifest.get("ingredient_name", "")).casefold()
            if ingredient not in ingredients:
                continue
            label_path = Path(str(manifest.get("label_path", "")))
            if not label_path.is_absolute():
                label_path = manifest_path.parent / label_path.name
            labels[ingredient] = xml_label_text(label_path.read_bytes())
        except (OSError, ValueError, KeyError):
            continue
    return labels


def build_top100_scientific_review(
    input_path: Path = DEFAULT_SIGNALS_CSV,
    output_path: Path = DEFAULT_REVIEW_CSV,
    report_path: Path = DEFAULT_REVIEW_REPORT,
    raw_dir: Path = DEFAULT_DAILYMED_RAW,
) -> list[dict[str, object]]:
    """Build the offline review CSV and its markdown summary."""
    with input_path.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    labels = _local_label_texts(
        raw_dir, {row["ingredient_name"].casefold() for row in source_rows}
    )
    reviewed = []
    for rank, source in enumerate(source_rows, start=1):
        row = {"rank": rank, **source}
        interpretation = interpret_scientific_signals(
            row, labels.get(source["ingredient_name"].casefold(), "")
        )
        reviewed.append({**row, **interpretation})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(reviewed)
    _write_report(reviewed, report_path)
    return reviewed


def _write_report(rows: list[dict[str, object]], report_path: Path) -> None:
    disposition = Counter(str(row["suggested_manual_disposition"]) for row in rows)
    toxicity = Counter(str(row["toxicity_signal_class"]) for row in rows)
    sensitivity = Counter(str(row["toxicity_formulation_sensitivity"]) for row in rows)
    specialist = Counter(
        flag
        for row in rows
        for flag in str(row["specialist_review_flags"]).split("; ")
        if flag
    )
    lines = [
        "# Top-100 Scientific Formulation-Rescue Review",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Purpose",
        "",
        "This fixed top-100 review refines Phase 3 label signals by separating potentially "
        "formulation-sensitive burdens from exposure-pattern, intrinsic, and specialist safety "
        "signals. It is hypothesis generation, not scientific, clinical, regulatory, legal, "
        "investment, or formulation validation.",
        "",
        "## Phase 3.1 interpretation",
        "",
        "- Toxicity fields classify dominant concern, formulation sensitivity, conflicts, and manual-review need.",
        "- PK/dosing fields capture schedule and kinetic language as review triggers; they do not prove short half-life or exposure causality.",
        "- Specialist flags identify oncology/cytotoxic, NTI, biologic, diagnostic, contrast, radiopharmaceutical, controlled-substance, and obsolete-antibiotic review needs.",
        "- Regulatory pathway fields are conservative screening placeholders, not regulatory advice.",
        "",
        "## Disposition vocabulary",
        "",
        "- `advance`: strong formulation-sensitive evidence without a severe conflicting signal; still unvalidated.",
        "- `literature_review`: plausible but mechanistically or clinically unresolved.",
        "- `specialist_category`: requires domain-specific safety and/or regulatory review.",
        "- `deprioritise`: weak or incomplete rescue rationale.",
        "- `reject`: clear artefact or strong evidence against rescue (none assigned automatically without such evidence).",
        "",
        "## Counts by suggested manual disposition",
        "",
    ]
    lines += [f"- {key}: {value}" for key, value in sorted(disposition.items())]
    lines += ["", "## Counts by toxicity signal class", ""]
    lines += [f"- {key}: {value}" for key, value in sorted(toxicity.items())]
    lines += ["", "## Counts by toxicity formulation sensitivity", ""]
    lines += [f"- {key}: {value}" for key, value in sorted(sensitivity.items())]
    lines += [
        "",
        "## Conflict and specialist counts",
        "",
        f"- Conflicting toxicity signals: {sum(int(row['has_conflicting_toxicity_signals']) for row in rows)}",
    ]
    lines += [f"- {key}: {value}" for key, value in sorted(specialist.items())]
    if not specialist:
        lines.append("- No specialist flags detected")
    lines += [
        "",
        "## Top 30 candidates",
        "",
        "| Rank | Ingredient | Triage | Score | Toxicity class | Sensitivity | Dominant concern | PK score | Regulatory pathway | Disposition | Hypothesis |",
        "|---:|---|---|---:|---|---|---|---:|---|---|---|",
    ]
    for row in rows[:30]:
        values = [
            row["rank"], row["ingredient_name"], row["triage_class"],
            row["scientific_rescue_signal_score"], row["toxicity_signal_class"],
            row["toxicity_formulation_sensitivity"], row["dominant_toxicity_concern"],
            row["score_pk_dosing_burden"], row["potential_regulatory_pathway"],
            row["suggested_manual_disposition"], row["candidate_hypothesis"],
        ]
        lines.append("| " + " | ".join(str(value).replace("|", "/") for value in values) + " |")
    lines += [
        "",
        "## Limitations",
        "",
        "- Keyword proximity and presence do not establish mechanism, severity, incidence, causality, or rescueability.",
        "- DailyMed matching may represent only one manufacturer, route, strength, or presentation.",
        "- PK language may refer to a metabolite or special population; detected terms require manual source-context review.",
        "- Absence of a detected term is not evidence that a burden or toxicity is absent.",
        "- Regulatory pathways, discontinuation causes, current clinical relevance, patents/FTO, feasibility, and comparator products remain unverified.",
        "",
        "## Next manual review workflow",
        "",
        "1. Route `specialist_category` rows to the named domain reviewer and resolve safety/regulatory constraints.",
        "2. Review conflict cases before crediting route, infusion, or handling burden as rescueable.",
        "3. For `literature_review`, assess exposure-toxicity and PK/PD evidence, including parent/metabolite and population context.",
        "4. For remaining candidates, confirm discontinuation reason, comparator landscape, formulation feasibility, and patent/FTO.",
        "5. Record a controlled `manual_disposition` and reviewer notes; do not treat the suggested disposition as validation.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
