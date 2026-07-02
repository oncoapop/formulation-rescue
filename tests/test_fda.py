import json
import zipfile

from formulation_rescue.database import connect
from formulation_rescue.fda import (
    download_file,
    ingest_drugs_fda,
    ingest_orange_book,
    sha256_file,
)


def _fixture_zip(source, destination):
    with zipfile.ZipFile(destination, "w") as archive:
        for path in sorted(source.iterdir()):
            archive.write(path, path.name)


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
