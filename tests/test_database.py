import csv
from datetime import date

from formulation_rescue.database import connect, initialize_database, score_phase1
from formulation_rescue.export import CSV_COLUMNS, export_phase1


def _insert_synthetic_data(db_path):
    with connect(db_path) as connection:
        source_id = connection.execute(
            """
            INSERT INTO source_files (
                source_name, source_url, local_path, sha256, downloaded_at
            ) VALUES ('Drugs@FDA', 'https://example.test', '/tmp/test.zip',
                      ?, '2026-01-01T00:00:00+00:00')
            """,
            ("0" * 64,),
        ).lastrowid
        ingredient_id = connection.execute(
            """
            INSERT INTO ingredients (ingredient_name, normalized_name, raw_json)
            VALUES ('Synthetic Ingredient', 'synthetic ingredient', '{"source":"test"}')
            """
        ).lastrowid
        product_id = connection.execute(
            """
            INSERT INTO products (
                application_number, product_number, proprietary_name, sponsor_name,
                dosage_form, route, marketing_status, is_discontinued, raw_json
            ) VALUES (
                'N000001', '001', 'Synthetic Product', 'Example Sponsor',
                'INJECTION', 'INTRAVENOUS', 'DISCONTINUED', 1, '{"source":"test"}'
            )
            """
        ).lastrowid
        connection.execute(
            """
            INSERT INTO product_ingredients (product_id, ingredient_id, strength)
            VALUES (?, ?, '10 mg/mL')
            """,
            (product_id, ingredient_id),
        )
        connection.execute(
            """
            INSERT INTO product_observations (
                product_id, source_file_id, source_name,
                active_in_latest_snapshot, application_type, sponsor_name,
                dosage_form_raw, route_raw, canonical_dosage_form,
                canonical_route, parenteral_route_signal,
                unknown_dosage_form, unknown_route, marketing_status,
                marketing_status_class, raw_active_ingredient, raw_strength,
                mapping_quality, observed_at
            ) VALUES (
                ?, ?, 'Drugs@FDA', 1, 'NDA', 'Example Sponsor',
                'INJECTION', 'INTRAVENOUS', 'injection', 'intravenous', 1,
                0, 0, 'Discontinued', 'discontinued',
                'Synthetic Ingredient', '10 mg/mL',
                'exact_single_ingredient', '2026-01-01T00:00:00+00:00'
            )
            """,
            (product_id, source_id),
        )
        connection.execute(
            """
            INSERT INTO patents (product_id, patent_number, patent_expiry)
            VALUES (?, 'TEST123', '2020-01-01')
            """,
            (product_id,),
        )


def test_database_scoring_and_export_are_offline(tmp_path):
    db_path = tmp_path / "test.sqlite"
    csv_path = tmp_path / "candidates.csv"
    report_path = tmp_path / "summary.md"
    initialize_database(db_path)
    _insert_synthetic_data(db_path)

    assert score_phase1(db_path, date(2026, 1, 1)) == 1
    assert export_phase1(db_path, csv_path, report_path) == 1

    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == CSV_COLUMNS
    assert rows[0]["ingredient_name"] == "Synthetic Ingredient"
    assert rows[0]["all_products_discontinued"] == "1"
    assert rows[0]["triage_class"] == "therapeutic_drug"
    assert rows[0]["score_total"] == "10"
    review_path = tmp_path / "candidates_science_review.csv"
    with review_path.open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 1
    assert "Candidates scored: 1" in report_path.read_text(encoding="utf-8")
    assert "Candidates tied at maximum: 1" in report_path.read_text(encoding="utf-8")
