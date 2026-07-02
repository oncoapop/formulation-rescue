import csv
from datetime import date

from formulation_rescue.database import connect, initialize_database, score_phase1
from formulation_rescue.export import CSV_COLUMNS, export_phase1


def _insert_synthetic_data(db_path):
    with connect(db_path) as connection:
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
    assert rows[0]["has_iv_only_or_injectable_only"] == "1"
    assert rows[0]["score_total"] == "11"
    assert "Candidates scored: 1" in report_path.read_text(encoding="utf-8")
