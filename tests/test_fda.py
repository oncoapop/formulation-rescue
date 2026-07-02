import json
import zipfile

import pytest

from formulation_rescue.database import connect, score_phase1
from formulation_rescue.fda import (
    canonicalize_routes,
    download_file,
    ingest_drugs_fda,
    ingest_orange_book,
    sha256_file,
)


def _fixture_zip(source, destination):
    with zipfile.ZipFile(destination, "w") as archive:
        for path in sorted(source.iterdir()):
            archive.write(path, path.name)


def _write_zip(destination, files):
    with zipfile.ZipFile(destination, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _drugs_files(
    *,
    status="Discontinued",
    application_rows="000010\tNDA\t\tExample Sponsor\n",
    active_ingredient="ONE DRUG",
    strength="10MG",
    form="INJECTABLE;SUBCUTANEOUS",
    application_no="000010",
):
    return {
        "Applications.txt": (
            "ApplNo\tApplType\tApplPublicNotes\tSponsorName\n" + application_rows
        ),
        "Products.txt": (
            "ApplNo\tProductNo\tForm\tStrength\tReferenceDrug\tDrugName\t"
            "ActiveIngredient\tReferenceStandard\n"
            f"{application_no}\t001\t{form}\t{strength}\t0\tTEST DRUG\t"
            f"{active_ingredient}\t0\n"
        ),
        "MarketingStatus.txt": (
            "MarketingStatusID\tApplNo\tProductNo\n"
            f"1\t{application_no}\t001\n"
        ),
        "MarketingStatus_Lookup.txt": (
            "MarketingStatusID\tMarketingStatusDescription\n" f"1\t{status}\n"
        ),
    }


def test_download_validates_archive_without_network(tmp_path, fixture_root):
    source = tmp_path / "source.zip"
    destination = tmp_path / "raw" / "orange_book.zip"
    _fixture_zip(fixture_root / "orange_book", source)

    result = download_file(
        source.as_uri(),
        destination,
        {"products.txt", "patent.txt", "exclusivity.txt"},
    )

    assert result == destination
    assert sha256_file(result) == sha256_file(source)
    assert not destination.with_suffix(".zip.part").exists()


def test_orange_book_ingestion_from_offline_zip(tmp_path, fixture_root):
    archive = tmp_path / "orange.zip"
    database = tmp_path / "test.sqlite"
    _fixture_zip(fixture_root / "orange_book", archive)

    counts = ingest_orange_book(archive, database)
    assert counts == {
        "products": 2,
        "ingredients": 3,
        "patents": 1,
        "exclusivities": 1,
    }

    with connect(database) as connection:
        source = connection.execute("SELECT * FROM source_files").fetchone()
        assert source["sha256"] == sha256_file(archive)
        product = connection.execute(
            "SELECT * FROM products WHERE application_number = 'NDA000002'"
        ).fetchone()
        assert product["route"] == "INTRAVENOUS"
        assert product["is_discontinued"] == 1
        assert json.loads(product["raw_json"])["Ingredient"].startswith("BETA")
        patent = connection.execute("SELECT * FROM patents").fetchone()
        assert patent["patent_expiry"] == "2030-01-01"

    assert ingest_orange_book(archive, database) == counts
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM patents").fetchone()[0] == 1


def test_drugs_fda_merges_products_and_status_offline(
    tmp_path, fixture_root
):
    orange = tmp_path / "orange.zip"
    drugs = tmp_path / "drugs.zip"
    database = tmp_path / "test.sqlite"
    _fixture_zip(fixture_root / "orange_book", orange)
    _fixture_zip(fixture_root / "drugs_fda", drugs)
    ingest_orange_book(orange, database)

    assert ingest_drugs_fda(drugs, database) == {
        "products": 2,
        "ingredients": 2,
    }
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 3
        alpha = connection.execute(
            "SELECT * FROM products WHERE application_number = 'NDA000001'"
        ).fetchone()
        assert alpha["sponsor_name"] == "Alpha Company Updated"
        delta = connection.execute(
            "SELECT * FROM products WHERE application_number = 'ANDA000003'"
        ).fetchone()
        assert delta["is_discontinued"] == 1
        assert connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 2


def test_newer_snapshot_retires_removed_and_updates_changed_ip(
    tmp_path, fixture_root
):
    database = tmp_path / "test.sqlite"
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    third = tmp_path / "third.zip"
    _fixture_zip(fixture_root / "orange_book", first)
    products = (fixture_root / "orange_book" / "products.txt").read_text()
    _write_zip(
        second,
        {
            "products.txt": products,
            "patent.txt": (
                "Appl_Type~Appl_No~Product_No~Patent_No~"
                "Patent_Expire_Date_Text~Drug_Substance_Flag~"
                "Drug_Product_Flag~Patent_Use_Code~Delist_Flag~Submission_Date\n"
                "N~000001~001~1234567~Jan 01, 2031~Y~Y~U-1~Y~Jan 2, 2020\n"
            ),
            "exclusivity.txt": (
                "Appl_Type~Appl_No~Product_No~Exclusivity_Code~Exclusivity_Date\n"
            ),
        },
    )
    _write_zip(
        third,
        {
            "products.txt": products,
            "patent.txt": (
                "Appl_Type~Appl_No~Product_No~Patent_No~"
                "Patent_Expire_Date_Text~Drug_Substance_Flag~"
                "Drug_Product_Flag~Patent_Use_Code~Delist_Flag~Submission_Date\n"
            ),
            "exclusivity.txt": (
                "Appl_Type~Appl_No~Product_No~Exclusivity_Code~Exclusivity_Date\n"
            ),
        },
    )

    ingest_orange_book(first, database)
    ingest_orange_book(second, database)
    with connect(database) as connection:
        patent = connection.execute("SELECT * FROM patents").fetchone()
        assert patent["patent_expiry"] == "2031-01-01"
        assert patent["ip_active_in_latest_snapshot"] == 1
        assert patent["delist_requested_signal"] == 1
        assert connection.execute(
            "SELECT ip_active_in_latest_snapshot FROM exclusivities"
        ).fetchone()[0] == 0
    ingest_orange_book(third, database)
    with connect(database) as connection:
        assert connection.execute(
            "SELECT ip_active_in_latest_snapshot FROM patents"
        ).fetchone()[0] == 0


def test_marketing_status_reversal_is_not_sticky(tmp_path):
    database = tmp_path / "test.sqlite"
    first = tmp_path / "discontinued.zip"
    second = tmp_path / "active.zip"
    _write_zip(first, _drugs_files(status="Discontinued"))
    _write_zip(second, _drugs_files(status="Prescription"))

    ingest_drugs_fda(first, database)
    ingest_drugs_fda(second, database)

    with connect(database) as connection:
        product = connection.execute("SELECT * FROM products").fetchone()
        assert product["is_discontinued"] == 0
        states = connection.execute(
            """
            SELECT active_in_latest_snapshot, COUNT(*)
            FROM product_observations GROUP BY active_in_latest_snapshot
            """
        ).fetchall()
        assert {tuple(row) for row in states} == {(0, 1), (1, 1)}


def test_source_disagreement_is_exportable(tmp_path, fixture_root):
    database = tmp_path / "test.sqlite"
    drugs = tmp_path / "drugs.zip"
    _write_zip(
        drugs,
        _drugs_files(
            status="Discontinued",
            application_rows="000001\tNDA\t\tAlpha Company\n",
            active_ingredient="ALPHA DRUG",
            application_no="000001",
            form="TABLET;ORAL",
        ),
    )
    ingest_orange_book(fixture_root / "orange_book", database)
    ingest_drugs_fda(drugs, database)
    score_phase1(database)
    with connect(database) as connection:
        candidate = connection.execute(
            """
            SELECT * FROM phase1_candidates
            WHERE ingredient_name = 'ALPHA DRUG'
            """
        ).fetchone()
        assert "marketing_status_disagreement" in candidate["source_conflict_flags"]
        assert candidate["all_products_discontinued"] == 1


def test_missing_application_type_is_inferred_only_from_unique_product(
    tmp_path, fixture_root
):
    database = tmp_path / "test.sqlite"
    drugs = tmp_path / "drugs.zip"
    _write_zip(
        drugs,
        _drugs_files(
            status="Prescription",
            application_rows="",
            active_ingredient="ALPHA DRUG",
            application_no="000001",
            form="TABLET;ORAL",
        ),
    )
    ingest_orange_book(fixture_root / "orange_book", database)
    ingest_drugs_fda(drugs, database)
    with connect(database) as connection:
        applications = connection.execute(
            """
            SELECT application_number FROM products
            WHERE product_number = '001' AND application_number LIKE '%000001'
            """
        ).fetchall()
        assert [row[0] for row in applications] == ["NDA000001"]


def test_ambiguous_multi_ingredient_strength_is_preserved(tmp_path):
    database = tmp_path / "test.sqlite"
    drugs = tmp_path / "drugs.zip"
    _write_zip(
        drugs,
        _drugs_files(
            status="Prescription",
            active_ingredient="ONE DRUG; TWO DRUG",
            strength="10MG",
        ),
    )
    ingest_drugs_fda(drugs, database)
    with connect(database) as connection:
        links = connection.execute(
            "SELECT * FROM product_ingredients ORDER BY ingredient_id"
        ).fetchall()
        assert len(links) == 2
        assert {row["mapping_quality"] for row in links} == {
            "ambiguous_multi_ingredient_strength"
        }
        assert all(row["strength"] is None for row in links)
        assert all(row["raw_strength"] == "10MG" for row in links)


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("IV", "intravenous"),
        ("INTRAMUSCULAR", "intramuscular"),
        ("SUBCUTANEOUS", "subcutaneous"),
        ("INTRA-ARTERIAL", "intra-arterial"),
        ("INTRATHECAL", "intrathecal"),
        ("EPIDURAL", "epidural"),
        ("INTRAVITREAL", "intravitreal"),
        ("INTRA-ARTICULAR", "intra-articular"),
        ("INTRAPERITONEAL", "intraperitoneal"),
        ("INJECTION", "injectable"),
    ],
)
def test_parenteral_route_variants(raw, canonical):
    routes, parenteral, unknown = canonicalize_routes(raw)
    assert routes == [canonical]
    assert parenteral is True
    assert unknown is False


def test_missing_required_header_fails_clearly(tmp_path):
    database = tmp_path / "test.sqlite"
    archive = tmp_path / "bad.zip"
    files = _drugs_files()
    files["Products.txt"] = "ApplNo\tProductNo\tForm\n000010\t001\tTABLET;ORAL\n"
    _write_zip(archive, files)
    with pytest.raises(ValueError, match="missing required columns"):
        ingest_drugs_fda(archive, database)
