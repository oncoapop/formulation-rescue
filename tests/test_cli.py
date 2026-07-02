from formulation_rescue.cli import main


def test_init_db_command(tmp_path):
    db_path = tmp_path / "cli.sqlite"

    assert main(["--db", str(db_path), "init-db"]) == 0
    assert db_path.exists()


def test_ingestion_commands_accept_offline_fixture_directories(
    tmp_path, fixture_root, capsys
):
    db_path = tmp_path / "cli.sqlite"
    assert main(
        [
            "--db",
            str(db_path),
            "ingest-orange-book",
            "--source",
            str(fixture_root / "orange_book"),
        ]
    ) == 0
    assert main(
        [
            "--db",
            str(db_path),
            "ingest-drugs-fda",
            "--source",
            str(fixture_root / "drugs_fda"),
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "products=2" in output
