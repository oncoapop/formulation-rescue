"""Build a portable, collaborator-facing review package without external I/O."""

from __future__ import annotations

import csv
import re
import shutil
import zipfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from .database import PROJECT_ROOT
from .rescueability import DEFAULT_RESCUEABILITY_CSV
from .scientific_review import DEFAULT_REVIEW_CSV

DEFAULT_EXPORT_ROOT = PROJECT_ROOT / "exports"
COPIED_REPORTS = (
    "top100_rescueability_review.md",
    "review_queues_summary.md",
    "top100_scientific_review.md",
    "phase3_label_enrichment_summary.md",
    "phase1_summary.md",
)
INDEX_COLUMNS = (
    "rank",
    "ingredient_name",
    "triage_class",
    "scientific_rescue_signal_score",
    "toxicity_signal_class",
    "toxicity_formulation_sensitivity",
    "dominant_toxicity_concern",
    "specialist_review_flags",
    "potential_regulatory_pathway",
    "suggested_manual_disposition",
    "candidate_packet_path",
)
MANUAL_COLUMNS = ("manual_disposition", "next_evidence_needed", "reviewer_notes")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    return safe[:100] or "UNNAMED"


def _md(value: object) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ")


def _yes(value: object) -> str:
    return "Yes" if str(value).casefold() in {"1", "true", "yes"} else "No"


def _packet_name(row: dict[str, str]) -> str:
    return f"{int(row['rank']):03d}_{_safe_name(row['ingredient_name'])}.md"


def _write_csv(path: Path, columns: tuple[str, ...] | list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _product_summary(row: dict[str, str]) -> str:
    return (
        f"{row.get('product_count', '0')} products: "
        f"{row.get('active_product_count', '0')} active and "
        f"{row.get('discontinued_product_count', '0')} discontinued; "
        f"all discontinued: {_yes(row.get('all_products_discontinued'))}; "
        f"mixed active/discontinued: {_yes(row.get('mixed_active_discontinued'))}."
    )


def _candidate_limitations(row: dict[str, str]) -> list[str]:
    limitations = [
        "Detected label terms are screening signals and do not establish mechanism, incidence, severity, or rescueability."
    ]
    if row.get("label_match_quality") not in {"exact", "high"}:
        limitations.append(
            f"DailyMed match quality is {row.get('label_match_quality') or 'unknown'}, limiting product-specific interpretation."
        )
    else:
        limitations.append(
            "The matched DailyMed label may represent only one manufacturer, strength, route, or presentation."
        )
    if row.get("pk_review_required") == "1":
        limitations.append(
            "Detected PK language requires source-context review and may describe a metabolite or special population."
        )
    if row.get("has_conflicting_toxicity_signals") == "1":
        limitations.append(
            "Formulation-sensitive and intrinsic/specialist signals overlap; route burden must not be treated as proof of rescueability."
        )
    if row.get("specialist_review_flags"):
        limitations.append(
            f"Specialist flags ({row['specialist_review_flags']}) require domain-specific safety and regulatory review."
        )
    limitations.append(
        "Regulatory pathway, discontinuation cause, clinical utility, patent/FTO, and formulation feasibility remain unverified."
    )
    return limitations


def _write_packet(path: Path, row: dict[str, str]) -> None:
    lines = [
        f"# Candidate {int(row['rank']):03d}: {row['ingredient_name']}",
        "",
        "## Review summary",
        "",
        f"- Rank: {row['rank']}",
        f"- Ingredient: {row['ingredient_name']}",
        f"- Triage: {row.get('triage_class', '')} / {row.get('triage_subclass', '')}",
        f"- Scientific rescue signal score: {row.get('scientific_rescue_signal_score', '')}",
        f"- Product/status summary: {_product_summary(row)}",
        f"- Routes: {row.get('canonical_route_list') or 'Not established'}",
        f"- Dosage forms: {row.get('canonical_dosage_form_list') or 'Not established'}",
        f"- DailyMed label match quality: {row.get('label_match_quality') or 'Not established'}",
        "",
        "## Detected evidence",
        "",
        f"- Administration burden terms: {row.get('administration_burden_terms') or 'None detected'}",
        f"- Safety burden terms: {row.get('safety_burden_terms') or 'None detected'}",
        f"- Formulation burden terms: {row.get('formulation_burden_terms') or 'None detected'}",
        f"- Toxicity signal class: {row.get('toxicity_signal_class')}",
        f"- Toxicity formulation sensitivity: {row.get('toxicity_formulation_sensitivity')}",
        f"- Dominant toxicity concern: {row.get('dominant_toxicity_concern')}",
        f"- Conflicting toxicity signals: {_yes(row.get('has_conflicting_toxicity_signals'))}",
        f"- Dosing-frequency terms: {row.get('dosing_frequency_terms') or 'None detected'}",
        f"- Half-life/PK terms: {row.get('half_life_or_pk_terms') or 'None detected'}",
        f"- PK/dosing burden score: {row.get('score_pk_dosing_burden') or '0'}",
        f"- PK context quality: {row.get('pk_context_quality') or 'Not established'}",
        f"- PK review required: {_yes(row.get('pk_review_required'))}",
        f"- Specialist review flags: {row.get('specialist_review_flags') or 'None'}",
        "",
        "## Interpretation and disposition",
        "",
        f"- Potential regulatory pathway placeholder: {row.get('potential_regulatory_pathway')}",
        f"- Regulatory pathway confidence: {row.get('regulatory_pathway_confidence')}",
        f"- Suggested manual disposition: {row.get('suggested_manual_disposition')}",
        f"- Candidate hypothesis: {row.get('candidate_hypothesis')}",
        f"- Next evidence needed: {row.get('next_evidence_needed')}",
        "",
        "## Phase 3.2 rescueability",
        "",
        f"- Rescueability score: {row.get('rescueability_score') or 'Not assessed'}",
        f"- Rescueability tier: {row.get('rescueability_tier') or 'Not assessed'}",
        f"- Review queue: {row.get('review_queue') or 'Not assessed'}",
        f"- Primary rescue hypothesis type: {row.get('primary_rescue_hypothesis_type') or 'Not assessed'}",
        f"- Family representative: {_yes(row.get('family_representative_flag'))}",
        f"- Family representative ingredient: {row.get('family_representative_ingredient') or 'Not assessed'}",
        f"- Independent duplicate-review reason: {row.get('duplicate_independent_review_reason') or 'None identified'}",
        f"- Rescueability notes: {row.get('rescueability_notes') or 'Not assessed'}",
        "",
        "## Reviewer notes",
        "",
        "- Manual disposition:",
        "- Reviewer:",
        "- Date:",
        "- Notes:",
        "",
        "## Candidate-specific limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in _candidate_limitations(row))
    lines.extend(
        [
            "",
            "This packet supports hypothesis generation only. It is not validated scientific, "
            "clinical, regulatory, legal, investment, or drug-development advice.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_readme(path: Path) -> None:
    path.write_text(
        """# Formulation-Rescue Top-100 Review Package

This portable package supports human scientific review of 100 formulation-rescue screening hypotheses derived from existing public FDA Orange Book, Drugs@FDA, and DailyMed evidence. It is a hypothesis-generation package, not validated drug-development, clinical, regulatory, legal, patent, investment, or medical advice.

## Read first

1. Start with `top100_rescueability_review.csv`; sort by `recommended_review_order`, then examine rescueability tier and review queue.
2. Open `top100_scientific_review.xlsx` for the underlying Phase 3.1 evidence and editable review columns.
3. Read `reports/top100_rescueability_review.md` and `reports/review_queues_summary.md` for Phase 3.2 summaries.
4. Read `reports/top100_scientific_review.md` for the Phase 3.1 burden interpretation.
5. Use `candidate_index.csv` to locate an individual file under `candidate_packets/`.
6. Consult `methods/` before interpreting scores or classifications.

## Phase 3.1 versus Phase 3.2

Phase 3.1 identifies label and product burden, including administration, handling, safety, toxicity, and PK/dosing review triggers. Phase 3.2 separately estimates whether that burden is plausibly modifiable through formulation, route, dosing, exposure profile, handling, device, storage, or presentation changes. A high Phase 3.1 scientific signal score does not imply high rescueability.

## Phase 3.2 review queues

- `small_molecule_reformulation`: general small-molecule formulation questions.
- `anti_infective_specialist`: infection, resistance, stewardship, or hospital-use context.
- `oncology_specialist`: cytotoxics and oncology biologics or ADCs.
- `biologic_delivery_specialist`: complex biologic, peptide, enzyme, protein, or toxin delivery.
- `immunology_biologic`: immune-mechanism and immunomodulator warning context.
- `acute_care_or_anaesthesia`: emergency, ICU, anaesthesia, paralytic, intrathecal, or acute administration.
- `deprioritise_or_false_positive`: weak links, contextual signals, or non-representative duplicates without an independent rationale.

## Rescueability tiers

- `A_strong_near_term_review`: strongest non-conflicted representatives for immediate review.
- `B_plausible_literature_review`: plausible but unresolved burden-to-fix hypotheses.
- `C_specialist_only_review`: oncology, biologic, NTI, or other specialist-dependent cases.
- `D_deprioritise`: weak, crowded, duplicate, or severely conflicted rationale.
- `E_likely_false_positive`: detected signal likely does not represent a formulation-rescue opportunity.

## Using the spreadsheet

`Top100 Review` contains the full review evidence. The final highlighted columns are intended for manual work: `manual_disposition`, `next_evidence_needed`, and `reviewer_notes`. Preserve controlled vocabulary in `manual_disposition`, document supporting evidence, and do not treat the generated suggestion as validation.

## Disposition vocabulary

- `advance`: strong formulation-sensitive evidence without a severe conflicting signal; still unvalidated.
- `literature_review`: plausible, but mechanistic or clinical evidence remains unresolved.
- `specialist_category`: domain-specific safety and/or regulatory review is required.
- `deprioritise`: current evidence provides a weak or incomplete formulation-rescue rationale.
- `reject`: a clear artefact or evidence strongly against formulation rescue; use only with documented justification.

## Toxicity formulation sensitivity

- `likely`: detected burden is plausibly route-local or formulation-sensitive.
- `possible`: exposure, route, excipient, concentration, handling, or formulation may contribute, but causality is unresolved.
- `conflicting`: formulation-sensitive evidence overlaps with intrinsic or specialist toxicity and must not create false optimism.
- `unlikely`: current evidence points primarily toward intrinsic or high-risk toxicity.
- `unknown`: available label evidence does not support a reliable interpretation.

## Limitations

Keyword signals do not establish causality or rescueability. DailyMed matching can be presentation-specific. PK language can concern metabolites or special populations. Discontinuation reasons, current clinical relevance, comparator products, formulation feasibility, patent/FTO, commercial value, and product-specific regulatory pathways were not validated. Absence of a detected term is not evidence that a burden is absent.
""",
        encoding="utf-8",
    )


METHOD_FILES = {
    "data_sources.md": """# Data Sources

The screening database uses locally retained public FDA-derived records already ingested by the project. FDA Orange Book records support product, application, patent, exclusivity, route, dosage-form, and marketing-status screening. Drugs@FDA records supplement approved-product and application context. DailyMed structured product labels provide label language used for administration, handling, safety, pediatric, and pharmacokinetic screening.

Ingredient-name and product mappings are imperfect. A DailyMed match can represent one manufacturer, strength, route, or presentation and is not necessarily exhaustive for an ingredient. No new source data were downloaded for this package.
""",
    "scoring_method.md": """# Screening and Scoring Method

Phase 1 aggregates products by conservatively normalized active ingredient and derives transparent component scores for IP openness, route gaps, discontinued or fragile supply, reformulation white space, and evidence completeness. Regulatory/product triage separates therapeutic products from categories requiring specialist interpretation.

Phase 3 adds rule-based DailyMed burden scores for administration, safety, formulation handling, pediatric gaps, route-conversion opportunity, and label-match confidence. The scientific rescue signal score ranks evidence for review; it is not a probability of technical or commercial success. Rank and score should not replace manual review.
""",
    "toxicity_interpretation_method.md": """# Toxicity and PK Interpretation Method

Phase 3.1 classifies detected label language into route-local, infusion-related, exposure-peak possible, systemic/intrinsic possible, organ toxicity, immunogenicity, oncology/cytotoxic, narrow-therapeutic-index, reproductive/genotoxicity, and unknown categories. A severity hierarchy prevents route or infusion signals from creating false optimism when intrinsic or specialist toxicity is also detected. Overlap cases are marked conflicting and routed to manual safety or specialist review.

Dosing schedules and PK terms—including half-life, Cmax, AUC, clearance, steady state, and metabolites—are review triggers. They do not prove short half-life, peak-driven toxicity, or suitability for modified release. Parent-drug, active-metabolite, and population-specific contexts require source and literature review.

Regulatory pathway values are conservative placeholders. They do not establish 505(b)(2) eligibility, biologic pathway, generic suitability, exclusivity, or approval probability.
""",
    "limitations.md": """# Limitations

This package supports hypothesis generation, not validation. Keyword presence does not establish mechanism, causality, clinical importance, incidence, severity, or formulation sensitivity. Keyword absence does not establish absence of risk.

Ingredient aggregation can obscure product-level differences. Labels may not cover all routes or presentations. Product marketing status does not explain discontinuation. Patent dates do not establish freedom to operate. The analysis does not validate formulation feasibility, stability, manufacturability, bioavailability, clinical utility, unmet need, commercial opportunity, comparator landscape, or regulatory strategy.

Every candidate requires manual label review, current literature and product-landscape review, and—where flagged—specialist safety and regulatory assessment before prioritization.
""",
    "rescueability_method.md": """# Phase 3.2 Rescueability Method

Phase 3.2 is a deterministic review-ranking layer distinct from the Phase 3.1 scientific burden score. It combines product status, route and administration burden, formulation handling, PK/dosing review triggers, label evidence quality, toxicity conflict, active-identity taxonomy, biologic or oncology complexity, and family-representative status.

Ingredient names are normalized for common salts and biologic suffixes before curated taxonomy checks. Classical cytotoxics, oncology biologics/ADCs, immunomodulators, anti-infectives, and acute-care products are routed separately. Obvious salt, biosimilar, suffix, and coformulation families retain every row, while deterministic representative selection reduces duplicate review. A duplicate receives independent consideration only when current records indicate a distinct route, presentation, coformulation, or other review rationale.

The rescueability score estimates review priority, not probability of success. Tiers and queues do not establish formulation feasibility, clinical utility, regulatory eligibility, patent freedom, commercial viability, or a validated development opportunity.
""",
}


def _write_methods(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in METHOD_FILES.items():
        (directory / name).write_text(body, encoding="utf-8")


def _excel_column(number: int) -> str:
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _sheet_xml(rows: list[list[object]], *, freeze: bool = False, autofilter: bool = False, editable_start: int | None = None) -> str:
    body = []
    for row_number, values in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(values, start=1):
            ref = f"{_excel_column(column_number)}{row_number}"
            style = 1 if row_number == 1 else 2 if editable_start and column_number >= editable_start else 0
            text = escape(str(value if value is not None else ""))
            cells.append(f'<c r="{ref}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{text}</t></is></c>')
        body.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    maximum = max((len(row) for row in rows), default=1)
    end = f"{_excel_column(maximum)}{max(len(rows), 1)}"
    views = '<sheetViews><sheetView workbookViewId="0">'
    if freeze:
        views += '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
    views += "</sheetView></sheetViews>"
    filter_xml = f'<autoFilter ref="A1:{end}"/>' if autofilter else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{end}"/>{views}<sheetFormatPr defaultRowHeight="15"/>'
        f'<sheetData>{"".join(body)}</sheetData>{filter_xml}</worksheet>'
    )


def _write_xlsx(path: Path, rows: list[dict[str, str]]) -> None:
    columns = [column for column in rows[0] if column not in MANUAL_COLUMNS] + list(MANUAL_COLUMNS)
    disposition = Counter(row["suggested_manual_disposition"] for row in rows)
    toxicity = Counter(row["toxicity_signal_class"] for row in rows)
    sheets = [
        (
            "Top100 Review",
            [columns] + [[row.get(column, "") for column in columns] for row in rows],
            True,
            True,
            len(columns) - len(MANUAL_COLUMNS) + 1,
        ),
        ("Disposition Counts", [["suggested_manual_disposition", "count"]] + [[key, value] for key, value in sorted(disposition.items())], True, True, None),
        ("Toxicity Class Counts", [["toxicity_signal_class", "count"]] + [[key, value] for key, value in sorted(toxicity.items())], True, True, None),
        (
            "Notes / Instructions",
            [
                ["Topic", "Instruction"],
                ["Purpose", "Hypothesis-generation review; not validated drug-development advice."],
                ["Manual columns", "Use the final highlighted columns in Top100 Review."],
                ["manual_disposition", "Use: advance, literature_review, specialist_category, deprioritise, or reject."],
                ["Suggested disposition", "Generated triage only; reviewers must document evidence and judgment."],
                ["PK terms", "Review triggers only; verify parent/metabolite and population context."],
                ["Regulatory pathway", "Conservative placeholder, not regulatory advice."],
            ],
            True,
            False,
            None,
        ),
    ]
    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    content_types.extend(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    content_types.append("</Types>")
    workbook_sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, *_rest) in enumerate(sheets, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{workbook_sheets}</sheets></workbook>"
    )
    workbook_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    workbook_rels.extend(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    workbook_rels.append(
        f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    )
    workbook_rels.append("</Relationships>")
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFFE699"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "".join(content_types))
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", "".join(workbook_rels))
        archive.writestr("xl/styles.xml", styles)
        for index, (_name, values, freeze, autofilter, editable_start) in enumerate(sheets, start=1):
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _sheet_xml(values, freeze=freeze, autofilter=autofilter, editable_start=editable_start),
            )


def _write_review_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    columns = (
        "rank", "ingredient_name", "scientific_rescue_signal_score",
        "toxicity_signal_class", "toxicity_formulation_sensitivity",
        "dominant_toxicity_concern", "potential_regulatory_pathway",
        "suggested_manual_disposition", "candidate_hypothesis",
    )
    lines = [
        "# Top-100 Scientific Review",
        "",
        "Hypothesis-generation screening table; not validated drug-development advice.",
        "",
        "| Rank | Ingredient | Score | Toxicity class | Formulation sensitivity | Dominant concern | Regulatory pathway placeholder | Suggested disposition | Candidate hypothesis |",
        "|---:|---|---:|---|---|---|---|---|---|",
    ]
    lines.extend("| " + " | ".join(_md(row[column]) for column in columns) + " |" for row in rows)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _manifest_description(relative: str) -> tuple[str, str]:
    if relative == "README.md":
        return "Package orientation and reviewer instructions.", "Generated from package specification."
    if relative == "MANIFEST.md":
        return "Complete package file inventory.", "Generated from package contents."
    if relative == "candidate_index.csv":
        return "Compact index of all candidate packets.", "Generated from the packaged top-100 review dataset."
    if relative == "top100_scientific_review.csv":
        return "Full Phase 3.1 review dataset.", str(DEFAULT_REVIEW_CSV.relative_to(PROJECT_ROOT))
    if relative == "top100_rescueability_review.csv":
        return "Full Phase 3.2 rescueability ranking and review queues.", str(DEFAULT_RESCUEABILITY_CSV.relative_to(PROJECT_ROOT))
    if relative == "top100_scientific_review.xlsx":
        return "Filterable review workbook with editable review columns.", "Generated from top100_scientific_review.csv."
    if relative == "top100_scientific_review.md":
        return "Readable top-100 candidate table.", "Generated from top100_scientific_review.csv."
    if relative.startswith("candidate_packets/"):
        return "Individual Phase 3.1 and Phase 3.2 candidate review packet.", "Generated from the packaged top-100 review dataset."
    if relative.startswith("reports/"):
        return "Project report retained for review context.", relative
    if relative.startswith("methods/"):
        return "Cautious manuscript-support method note.", "Generated from existing project methodology."
    return "Review package file.", "Generated locally."


def _write_manifest(package: Path, generated_at: str) -> None:
    manifest = package / "MANIFEST.md"
    if not manifest.exists():
        manifest.write_text("", encoding="utf-8")
    for _ in range(5):
        files = sorted(path for path in package.rglob("*") if path.is_file())
        lines = [
            "# Package Manifest",
            "",
            f"Generation timestamp: {generated_at}",
            "",
            "| Path | Size (bytes) | Description | Source | Generated |",
            "|---|---:|---|---|---|",
        ]
        for file_path in files:
            relative = file_path.relative_to(package).as_posix()
            description, source = _manifest_description(relative)
            lines.append(
                f"| `{relative}` | {file_path.stat().st_size} | {description} | `{source}` | {generated_at} |"
            )
        content = "\n".join(lines) + "\n"
        previous_size = manifest.stat().st_size
        manifest.write_text(content, encoding="utf-8")
        if manifest.stat().st_size == previous_size:
            break


def build_review_package(
    review_csv: Path = DEFAULT_REVIEW_CSV,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    package_date: date | None = None,
    *,
    rescueability_csv: Path | None = None,
    package_name: str | None = None,
) -> dict[str, object]:
    """Create the directory and ZIP archive for the existing fixed review set."""
    package_date = package_date or date.today()
    name = package_name or f"formulation_rescue_review_package_{package_date:%Y%m%d}"
    package = export_root / name
    package.mkdir(parents=True, exist_ok=True)
    generated_at = _timestamp()
    with review_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = list(reader.fieldnames or [])
    if len(rows) != 100:
        raise ValueError(f"Expected fixed top-100 review input; found {len(rows)} rows")
    packet_rows = rows
    if rescueability_csv is not None:
        with rescueability_csv.open(newline="", encoding="utf-8") as handle:
            rescueability_reader = csv.DictReader(handle)
            packet_rows = list(rescueability_reader)
        if len(packet_rows) != 100:
            raise ValueError(
                f"Expected fixed top-100 rescueability input; found {len(packet_rows)} rows"
            )

    _write_readme(package / "README.md")
    shutil.copyfile(review_csv, package / "top100_scientific_review.csv")
    if rescueability_csv is not None:
        shutil.copyfile(
            rescueability_csv, package / "top100_rescueability_review.csv"
        )
    _write_xlsx(package / "top100_scientific_review.xlsx", rows)
    _write_review_markdown(package / "top100_scientific_review.md", rows)

    packets = package / "candidate_packets"
    packets.mkdir(exist_ok=True)
    index_rows = []
    for row in packet_rows:
        packet_relative = f"candidate_packets/{_packet_name(row)}"
        _write_packet(package / packet_relative, row)
        index_rows.append({**row, "candidate_packet_path": packet_relative})
    _write_csv(package / "candidate_index.csv", INDEX_COLUMNS, index_rows)

    reports = package / "reports"
    reports.mkdir(exist_ok=True)
    for report_name in COPIED_REPORTS:
        source = PROJECT_ROOT / "reports" / report_name
        if source.exists():
            shutil.copyfile(source, reports / report_name)
    _write_methods(package / "methods")
    _write_manifest(package, generated_at)

    archive_path = export_root / f"{name}.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(path for path in package.rglob("*") if path.is_file()):
            archive.write(file_path, Path(name) / file_path.relative_to(package))
    return {
        "package_path": package,
        "zip_path": archive_path,
        "candidate_packets": len(list(packets.glob("*.md"))),
        "file_count": len(list(path for path in package.rglob("*") if path.is_file())),
        "zip_size": archive_path.stat().st_size,
        "columns": columns,
    }
