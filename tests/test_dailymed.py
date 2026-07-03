import csv
import json
import shutil
from pathlib import Path

from formulation_rescue.database import connect, score_phase1
from formulation_rescue.dailymed import (
    LABEL_COLUMNS,
    SIGNAL_COLUMNS,
    download_dailymed_labels,
    export_scientific_rescue_signals,
    extract_label_evidence,
    ingest_dailymed_labels,
    label_component_scores,
    label_match_quality,
    score_label_burden,
    xml_label_text,
)
from formulation_rescue.fda import ingest_drugs_fda, ingest_orange_book


def test_burden_label_detection(fixture_root):
    xml = (fixture_root / "dailymed" / "burden_label.xml").read_bytes()
    evidence = extract_label_evidence(xml_label_text(xml))

    assert evidence["has_boxed_warning"] == 1
    assert evidence["has_reconstitution_signal"] == 1
    assert evidence["has_infusion_or_injection_reaction_signal"] == 1
    assert evidence["has_hypersensitivity_signal"] == 1
    assert evidence["has_refrigeration_signal"] == 1
    assert evidence["has_storage_burden_signal"] == 1
    assert evidence["has_light_protection_signal"] == 1
    assert evidence["has_short_post_reconstitution_stability_signal"] == 1
    assert evidence["has_pediatric_gap_signal"] == 1
    assert evidence["has_renal_hepatic_adjustment_signal"] == 1


def test_low_quality_and_no_match_handling():
    assert label_match_quality("ALBIGLUTIDE", "ALBIGLUTIDE INJECTION") == "exact"
    assert label_match_quality("ALBIGLUTIDE", "ALBIGLUTIDE ACETATE") == "exact"
    assert label_match_quality("ALBIGLUTIDE", "UNRELATED TABLET") == "no_match"
    assert label_match_quality(
        "COMPLEX DRUG COMPONENT", "COMPLEX TABLET"
    ) == "low"


def test_label_component_score_calculation(fixture_root):
    evidence = {
        **extract_label_evidence(
            xml_label_text(
                (fixture_root / "dailymed" / "burden_label.xml").read_bytes()
            )
        ),
        "label_match_quality": "exact",
    }
    scores = label_component_scores(
        evidence, {"parenteral_route_signal": 1}
    )

    assert scores == {
        "score_administration_burden": 3,
        "score_safety_burden": 3,
        "score_formulation_handling_burden": 3,
        "score_pediatric_gap": 2,
        "score_route_conversion_opportunity": 3,
        "score_label_evidence_confidence": 3,
    }


def test_cached_download_does_not_use_network(tmp_path):
    input_csv = tmp_path / "review.csv"
    raw_dir = tmp_path / "raw"
    ingredient_dir = raw_dir / "alpha"
    ingredient_dir.mkdir(parents=True)
    input_csv.write_text("ingredient_name\nALPHA DRUG\n", encoding="utf-8")
    (ingredient_dir / "manifest.json").write_text(
        json.dumps(
            {
                "ingredient_name": "ALPHA DRUG",
                "status": "no_match",
                "label_match_quality": "no_match",
            }
        ),
        encoding="utf-8",
    )
    # The cache directory name is deterministic, so place the manifest there.
    from formulation_rescue.dailymed import _safe_stem

    target = raw_dir / _safe_stem("ALPHA DRUG")
    target.mkdir()
    shutil.copy(ingredient_dir / "manifest.json", target / "manifest.json")

    counts = download_dailymed_labels(
        input_csv, raw_dir, delay_seconds=0
    )
    assert counts["cached"] == 1
    assert counts["no_match"] == 1


def test_dailymed_ingest_score_and_export_columns(
    tmp_path, fixture_root
):
    database = tmp_path / "test.sqlite"
    raw_dir = tmp_path / "dailymed"
    enriched = tmp_path / "enriched.csv"
    signals = tmp_path / "signals.csv"
    report = tmp_path / "summary.md"
    ingest_orange_book(fixture_root / "orange_book", database)
    ingest_drugs_fda(fixture_root / "drugs_fda", database)
    score_phase1(database)

    directory = raw_dir / "alpha"
    directory.mkdir(parents=True)
    label_path = directory / "label.xml"
    shutil.copy(fixture_root / "dailymed" / "burden_label.xml", label_path)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "ingredient_name": "ALPHA DRUG",
                "status": "matched",
                "label_match_quality": "exact",
                "setid": "fixture-setid",
                "title": "ALPHA DRUG INJECTION",
                "published_date": "Jan 01, 2026",
                "label_path": str(label_path),
                "metadata_path": str(directory / "metadata.json"),
            }
        ),
        encoding="utf-8",
    )

    assert ingest_dailymed_labels(raw_dir, database)["matched"] == 1
    assert score_label_burden(database) == 4
    counts = export_scientific_rescue_signals(
        database, enriched, signals, report, limit=10
    )
    assert counts["matched"] == 1

    with enriched.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert set(LABEL_COLUMNS).issubset(reader.fieldnames)
    alpha = next(row for row in rows if row["ingredient_name"] == "ALPHA DRUG")
    assert alpha["has_boxed_warning"] == "1"
    assert int(alpha["scientific_rescue_signal_score"]) > 0
    with signals.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames) == SIGNAL_COLUMNS
    assert "hypothesis generation" in report.read_text(encoding="utf-8")


def test_no_match_receives_zero_confidence(tmp_path, fixture_root):
    database = tmp_path / "test.sqlite"
    raw_dir = tmp_path / "dailymed"
    ingest_orange_book(fixture_root / "orange_book", database)
    ingest_drugs_fda(fixture_root / "drugs_fda", database)
    score_phase1(database)
    directory = raw_dir / "beta"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "ingredient_name": "BETA DRUG",
                "status": "no_match",
                "label_match_quality": "no_match",
            }
        ),
        encoding="utf-8",
    )
    ingest_dailymed_labels(raw_dir, database)
    score_label_burden(database)
    with connect(database) as connection:
        row = connection.execute(
            """
            SELECT * FROM dailymed_label_evidence
            WHERE ingredient_name = 'BETA DRUG'
            """
        ).fetchone()
        assert row["score_label_evidence_confidence"] == 0
