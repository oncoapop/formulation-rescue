"""Deterministic Phase 2.2 scientific-review triage classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class TriageResult:
    triage_class: str
    triage_subclass: str
    exclude_from_top_science_review: bool
    exclusion_reason: str
    science_review_priority: str


_CONTRAST = re.compile(
    r"\b(METRIZOATE|IOHEXOL|IOPAMIDOL|DIATRIZOATE|IODIXANOL|IOVERSOL|"
    r"IOTHALAMATE|IOPROMIDE|IOPENTOL|GADOLINIUM|GADOBUTROL|GADOTERATE|"
    r"GADOTERIDOL|GADODIAMIDE|GADOBENATE|GADOXETATE)\b"
)
_RADIO = re.compile(
    r"(\bI[- ]?1(?:23|25|31)\b|\bCR[- ]?51\b|\bTC[- ]?99M?\b|"
    r"\bIN[- ]?111\b|\bGA[- ]?67\b|\bTL[- ]?201\b|\bINDIUM\b|"
    r"\bGALLIUM\b|\bTHALLIUM\b|\bRADIO[A-Z]*\b|\bCHROMATED\b|"
    r"\bIODINATED\b)"
)
_ELECTROLYTE = re.compile(
    r"^(CALCIUM|POTASSIUM|SODIUM CHLORIDE|MAGNESIUM|ZINC|PHOSPHATE|"
    r"DEXTROSE|WATER)(\b|$)"
)
_BLOOD = re.compile(
    r"\b(ALBUMIN( HUMAN)?|SERUM ALBUMIN|PLASMA|WHOLE BLOOD|"
    r"COAGULATION FACTOR|ANTIHEMOPHILIC FACTOR|IMMUNE GLOBULIN)\b"
)
_VACCINE = re.compile(
    r"\b(VACCINE|TOXOID|ANTIVENIN|ANTITOXIN|TUBERCULIN|"
    r"ALLERGENIC EXTRACT|SKIN TEST ANTIGEN)\b"
)
_DIAGNOSTIC = re.compile(
    r"\b(DIAGNOSTIC|FLUORESCEIN|INDOCYANINE GREEN|"
    r"COEXISTENCE ASSAY|SKIN TEST|BREATH TEST)\b"
)
_DEVICE_LIKE = re.compile(
    r"\b(IRRIGATION|DIALYSIS|CATHETER|LUBRICANT|SURGICAL|"
    r"ADHESIVE|SEALANT|BONE CEMENT|DEVICE)\b"
)
_CONTROLLED = re.compile(
    r"\b(FENTANYL|MORPHINE|OXYCODONE|HYDROCODONE|HYDROMORPHONE|"
    r"METHADONE|BUPRENORPHINE|AMPHETAMINE|METHAMPHETAMINE|"
    r"COCAINE|KETAMINE|PENTOBARBITAL|SECOBARBITAL)\b"
)
_OBSOLETE_ANTIBIOTIC = re.compile(
    r"\b(CEFAMANDOLE|CEFMENOXIME|CEFMETAZOLE|AZLOCILLIN|"
    r"CARBENICILLIN|TICARCILLIN|MEZLOCILLIN|METHICILLIN|"
    r"NAFCILLIN|KANAMYCIN|CHLORAMPHENICOL|DORIPENEM)\b"
)
_BIOLOGIC_NAME = re.compile(
    r"(MAB|CEPT|TIDE|GLUTIDE|INTERFERON|INTERLEUKIN|"
    r"ERYTHROPOIETIN|INSULIN|SOMATROPIN|ENZYME)$"
)

_EXCLUDED_CLASSES = {
    "electrolyte_mineral_nutrient",
    "diagnostic_agent",
    "radiopharmaceutical",
    "contrast_agent",
    "blood_or_albumin_product",
    "vaccine_or_immunologic",
    "device_like_or_procedure_agent",
}


def _base_priority(score_total: int) -> str:
    if score_total >= 7:
        return "high"
    if score_total >= 4:
        return "medium"
    return "low"


def classify_candidate(
    evidence: Mapping[str, object], score_total: int
) -> TriageResult:
    name = str(evidence.get("ingredient_name", "")).upper().strip()
    application_types = str(evidence.get("application_type_list", "")).upper()
    routes = str(evidence.get("canonical_route_list", "")).lower()
    forms = str(evidence.get("canonical_dosage_form_list", "")).lower()

    if _CONTRAST.search(name):
        category, subclass = "contrast_agent", (
            "gadolinium_contrast" if "GADO" in name else "iodinated_contrast"
        )
    elif _RADIO.search(name):
        category, subclass = "radiopharmaceutical", "radioisotope_or_labeled_agent"
    elif _VACCINE.search(name):
        category, subclass = "vaccine_or_immunologic", "vaccine_or_test_antigen"
    elif _BLOOD.search(name):
        category, subclass = "blood_or_albumin_product", "plasma_derived_or_albumin"
    elif _ELECTROLYTE.search(name):
        if name.startswith(("DEXTROSE", "WATER")):
            subclass = "carbohydrate_or_vehicle"
        else:
            subclass = "electrolyte_or_mineral"
        category = "electrolyte_mineral_nutrient"
    elif _DIAGNOSTIC.search(name):
        category, subclass = "diagnostic_agent", "nonradioactive_diagnostic"
    elif _DEVICE_LIKE.search(name) or "irrigation" in routes:
        category, subclass = (
            "device_like_or_procedure_agent",
            "procedure_or_device_adjunct",
        )
    elif _CONTROLLED.search(name):
        category, subclass = (
            "controlled_substance_or_abuse_risk",
            "controlled_or_abuse_liability",
        )
    elif _OBSOLETE_ANTIBIOTIC.search(name):
        category, subclass = "obsolete_antibiotic", "legacy_systemic_antibiotic"
    elif "BLA" in application_types or _BIOLOGIC_NAME.search(name):
        category, subclass = "biologic_or_peptide", (
            "peptide" if name.endswith(("TIDE", "GLUTIDE")) else "biologic"
        )
    elif name and (application_types or routes or forms):
        category, subclass = "therapeutic_drug", "small_molecule_or_other_therapeutic"
    else:
        category, subclass = "unclear_needs_review", "insufficient_classification_evidence"

    excluded = category in _EXCLUDED_CLASSES
    reason = (
        f"{category} is outside the initial therapeutic formulation-science review"
        if excluded
        else ""
    )
    priority = "excluded" if excluded else _base_priority(score_total)
    if category in {"controlled_substance_or_abuse_risk", "obsolete_antibiotic"}:
        priority = "medium" if priority == "high" else priority
    if category == "unclear_needs_review":
        priority = "medium"
    return TriageResult(category, subclass, excluded, reason, priority)
