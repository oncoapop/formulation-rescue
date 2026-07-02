"""Download and ingest the public Orange Book and Drugs@FDA data files."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, TextIO

from .database import DEFAULT_DB, PROJECT_ROOT, connect, initialize_database

ORANGE_BOOK_URL = "https://www.fda.gov/media/76860/download?attachment="
DRUGS_FDA_URL = "https://www.fda.gov/media/89850/download?attachment="
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_ORANGE_BOOK_ARCHIVE = DEFAULT_RAW_DIR / "orange_book.zip"
DEFAULT_DRUGS_FDA_ARCHIVE = DEFAULT_RAW_DIR / "drugsatfda.zip"

_ORANGE_REQUIRED = {"products.txt", "patent.txt", "exclusivity.txt"}
_DRUGS_REQUIRED = {
    "applications.txt",
    "products.txt",
    "marketingstatus.txt",
    "marketingstatus_lookup.txt",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _zip_members(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return {Path(name).name.lower() for name in archive.namelist() if not name.endswith("/")}


def _validate_archive(path: Path, required: set[str]) -> None:
    try:
        missing = required - _zip_members(path)
    except zipfile.BadZipFile as error:
        raise ValueError(f"{path} is not a valid ZIP archive") from error
    if missing:
        raise ValueError(f"{path} is missing required files: {', '.join(sorted(missing))}")


def download_file(
    url: str,
    destination: Path,
    required_members: set[str],
    timeout: int = 120,
) -> Path:
    """Download one immutable public archive, validating before replacement."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "formulation-rescue/0.2 (public FDA data download)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with temporary.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
        _validate_archive(temporary, required_members)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def download_orange_book(
    destination: Path = DEFAULT_ORANGE_BOOK_ARCHIVE,
    url: str = ORANGE_BOOK_URL,
) -> Path:
    return download_file(url, destination, _ORANGE_REQUIRED)


@contextmanager
def _open_table(source: Path, filename: str, delimiter: str) -> Iterator[TextIO]:
    """Open a named table from a ZIP or an extracted fixture directory."""
    if source.is_dir():
        matches = {path.name.lower(): path for path in source.iterdir()}
        path = matches.get(filename.lower())
        if path is None:
            raise FileNotFoundError(f"{filename} not found in {source}")
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            yield handle
        return

    with zipfile.ZipFile(source) as archive:
        matches = {
            Path(name).name.lower(): name
            for name in archive.namelist()
            if not name.endswith("/")
        }
        member = matches.get(filename.lower())
        if member is None:
            raise FileNotFoundError(f"{filename} not found in {source}")
        with archive.open(member) as binary:
            with io.TextIOWrapper(
                binary, encoding="utf-8-sig", errors="replace", newline=""
            ) as handle:
                yield handle


def _rows(source: Path, filename: str, delimiter: str) -> Iterator[dict[str, str]]:
    with _open_table(source, filename, delimiter) as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError(f"{filename} has no header")
        for source_row in reader:
            yield {
                (key or "").strip(): (value or "").strip()
                for key, value in source_row.items()
            }


def _field(row: dict[str, str], *names: str) -> str:
    normalized = {
        re.sub(r"[^a-z0-9]", "", key.casefold()): value for key, value in row.items()
    }
    for name in names:
        value = normalized.get(re.sub(r"[^a-z0-9]", "", name.casefold()))
        if value is not None:
            return value.strip()
    return ""


def _iso_date(value: str) -> str | None:
    value = value.strip()
    if not value or "prior to" in value.casefold():
        return None
    for pattern in ("%b %d, %Y", "%b %d %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognized FDA date: {value!r}")


def _application_number(number: str, application_type: str = "") -> str:
    digits = re.sub(r"\D", "", number).zfill(6)
    kind = application_type.strip().upper()
    if kind in {"N", "NDA"}:
        prefix = "NDA"
    elif kind in {"A", "ANDA"}:
        prefix = "ANDA"
    elif kind:
        prefix = kind
    else:
        prefix = "FDA"
    return f"{prefix}{digits}"


def _register_source(
    connection: sqlite3.Connection,
    source_name: str,
    source_url: str,
    source: Path,
) -> int:
    digest = sha256_file(source) if source.is_file() else _sha256_directory(source)
    downloaded_at = (
        datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat()
    )
    connection.execute(
        """
        INSERT INTO source_files (
            source_name, source_url, local_path, sha256, downloaded_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_name, sha256) DO UPDATE SET
            source_url = excluded.source_url,
            local_path = excluded.local_path
        """,
        (source_name, source_url, str(source.resolve()), digest, downloaded_at),
    )
    return connection.execute(
        "SELECT id FROM source_files WHERE source_name = ? AND sha256 = ?",
        (source_name, digest),
    ).fetchone()["id"]


def _sha256_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(item for item in path.iterdir() if item.is_file()):
        digest.update(child.name.encode())
        digest.update(child.read_bytes())
    return digest.hexdigest()


def _ingredient_id(
    connection: sqlite3.Connection, name: str, raw_json: str
) -> int:
    cleaned = " ".join(name.split())
    normalized = cleaned.casefold()
    existing = connection.execute(
        "SELECT id FROM ingredients WHERE normalized_name = ?", (normalized,)
    ).fetchone()
    if existing:
        return existing["id"]
    return connection.execute(
        """
        INSERT INTO ingredients (ingredient_name, normalized_name, raw_json)
        VALUES (?, ?, ?)
        """,
        (cleaned, normalized, raw_json),
    ).lastrowid


def _split_ingredients(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _upsert_product(
    connection: sqlite3.Connection,
    *,
    application_number: str,
    product_number: str,
    proprietary_name: str,
    sponsor_name: str,
    dosage_form: str,
    route: str,
    marketing_status: str,
    is_discontinued: bool,
    source_file_id: int,
    raw_json: str,
) -> int:
    connection.execute(
        """
        INSERT INTO products (
            application_number, product_number, proprietary_name, sponsor_name,
            dosage_form, route, marketing_status, is_discontinued,
            source_file_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(application_number, product_number) DO UPDATE SET
            proprietary_name = COALESCE(NULLIF(excluded.proprietary_name, ''),
                                        products.proprietary_name),
            sponsor_name = COALESCE(NULLIF(excluded.sponsor_name, ''),
                                    products.sponsor_name),
            dosage_form = COALESCE(NULLIF(excluded.dosage_form, ''),
                                   products.dosage_form),
            route = COALESCE(NULLIF(excluded.route, ''), products.route),
            marketing_status = COALESCE(NULLIF(excluded.marketing_status, ''),
                                        products.marketing_status),
            is_discontinued = MAX(products.is_discontinued,
                                  excluded.is_discontinued),
            source_file_id = excluded.source_file_id,
            raw_json = excluded.raw_json
        """,
        (
            application_number,
            product_number,
            proprietary_name,
            sponsor_name,
            dosage_form,
            route,
            marketing_status,
            int(is_discontinued),
            source_file_id,
            raw_json,
        ),
    )
    return connection.execute(
        """
        SELECT id FROM products
        WHERE application_number = ? AND product_number = ?
        """,
        (application_number, product_number),
    ).fetchone()["id"]


def ingest_orange_book(
    source: Path = DEFAULT_ORANGE_BOOK_ARCHIVE,
    db_path: Path = DEFAULT_DB,
) -> dict[str, int]:
    if source.is_file():
        _validate_archive(source, _ORANGE_REQUIRED)
    initialize_database(db_path)
    counts = {"products": 0, "ingredients": 0, "patents": 0, "exclusivities": 0}
    with connect(db_path) as connection:
        source_id = _register_source(
            connection, "FDA Orange Book", ORANGE_BOOK_URL, source
        )
        for row in _rows(source, "products.txt", "~"):
            raw = json.dumps(row, ensure_ascii=False, sort_keys=True)
            application = _application_number(
                _field(row, "Appl_No"), _field(row, "Appl_Type")
            )
            form_route = _field(row, "DF;Route")
            dosage_form, _, route = form_route.partition(";")
            product_id = _upsert_product(
                connection,
                application_number=application,
                product_number=_field(row, "Product_No"),
                proprietary_name=_field(row, "Trade_Name"),
                sponsor_name=_field(row, "Applicant_Full_Name", "Applicant"),
                dosage_form=dosage_form,
                route=route,
                marketing_status=_field(row, "Type"),
                is_discontinued=_field(row, "Type").upper() == "DISCN",
                source_file_id=source_id,
                raw_json=raw,
            )
            for ingredient in _split_ingredients(_field(row, "Ingredient")):
                ingredient_id = _ingredient_id(connection, ingredient, raw)
                connection.execute(
                    """
                    INSERT INTO product_ingredients (
                        product_id, ingredient_id, strength, raw_json
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(product_id, ingredient_id) DO UPDATE SET
                        strength = excluded.strength,
                        raw_json = excluded.raw_json
                    """,
                    (product_id, ingredient_id, _field(row, "Strength"), raw),
                )
                counts["ingredients"] += 1
            counts["products"] += 1

        product_ids = {
            (row["application_number"], row["product_number"]): row["id"]
            for row in connection.execute(
                "SELECT id, application_number, product_number FROM products"
            )
        }
        for row in _rows(source, "patent.txt", "~"):
            key = (
                _application_number(_field(row, "Appl_No"), _field(row, "Appl_Type")),
                _field(row, "Product_No"),
            )
            product_id = product_ids.get(key)
            if product_id is None:
                continue
            raw = json.dumps(row, ensure_ascii=False, sort_keys=True)
            connection.execute(
                """
                INSERT INTO patents (
                    product_id, patent_number, patent_expiry, use_code,
                    source_file_id, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, patent_number, use_code) DO UPDATE SET
                    patent_expiry = excluded.patent_expiry,
                    source_file_id = excluded.source_file_id,
                    raw_json = excluded.raw_json
                """,
                (
                    product_id,
                    _field(row, "Patent_No"),
                    _iso_date(_field(row, "Patent_Expire_Date_Text", "Patent_Expire_Date")),
                    _field(row, "Patent_Use_Code"),
                    source_id,
                    raw,
                ),
            )
            counts["patents"] += 1

        for row in _rows(source, "exclusivity.txt", "~"):
            key = (
                _application_number(_field(row, "Appl_No"), _field(row, "Appl_Type")),
                _field(row, "Product_No"),
            )
            product_id = product_ids.get(key)
            if product_id is None:
                continue
            raw = json.dumps(row, ensure_ascii=False, sort_keys=True)
            connection.execute(
                """
                INSERT INTO exclusivities (
                    product_id, exclusivity_code, exclusivity_expiry,
                    source_file_id, raw_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(
                    product_id, exclusivity_code, exclusivity_expiry
                ) DO UPDATE SET
                    source_file_id = excluded.source_file_id,
                    raw_json = excluded.raw_json
                """,
                (
                    product_id,
                    _field(row, "Exclusivity_Code"),
                    _iso_date(_field(row, "Exclusivity_Date")),
                    source_id,
                    raw,
                ),
            )
            counts["exclusivities"] += 1
    return counts


def ingest_drugs_fda(
    source: Path = DEFAULT_DRUGS_FDA_ARCHIVE,
    db_path: Path = DEFAULT_DB,
) -> dict[str, int]:
    if source.is_file():
        _validate_archive(source, _DRUGS_REQUIRED)
    initialize_database(db_path)
    applications = {
        _field(row, "ApplNo"): row
        for row in _rows(source, "Applications.txt", "\t")
    }
    status_names = {
        _field(row, "MarketingStatusID"): _field(
            row, "MarketingStatusDescription"
        )
        for row in _rows(source, "MarketingStatus_Lookup.txt", "\t")
    }
    statuses = {
        (_field(row, "ApplNo"), _field(row, "ProductNo")): status_names.get(
            _field(row, "MarketingStatusID"), ""
        )
        for row in _rows(source, "MarketingStatus.txt", "\t")
    }
    counts = {"products": 0, "ingredients": 0}
    with connect(db_path) as connection:
        source_id = _register_source(
            connection, "Drugs@FDA", DRUGS_FDA_URL, source
        )
        for row in _rows(source, "Products.txt", "\t"):
            application_row = applications.get(_field(row, "ApplNo"), {})
            application = _application_number(
                _field(row, "ApplNo"), _field(application_row, "ApplType")
            )
            form_route = _field(row, "Form")
            dosage_form, _, route = form_route.partition(";")
            status = statuses.get(
                (_field(row, "ApplNo"), _field(row, "ProductNo")), ""
            )
            combined_raw = {
                "product": row,
                "application": application_row,
                "marketing_status": status,
            }
            raw = json.dumps(combined_raw, ensure_ascii=False, sort_keys=True)
            product_id = _upsert_product(
                connection,
                application_number=application,
                product_number=_field(row, "ProductNo"),
                proprietary_name=_field(row, "DrugName"),
                sponsor_name=_field(application_row, "SponsorName"),
                dosage_form=dosage_form,
                route=route,
                marketing_status=status,
                is_discontinued="discontinued" in status.casefold(),
                source_file_id=source_id,
                raw_json=raw,
            )
            for ingredient in _split_ingredients(_field(row, "ActiveIngredient")):
                ingredient_id = _ingredient_id(connection, ingredient, raw)
                connection.execute(
                    """
                    INSERT INTO product_ingredients (
                        product_id, ingredient_id, strength, raw_json
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(product_id, ingredient_id) DO UPDATE SET
                        strength = excluded.strength,
                        raw_json = excluded.raw_json
                    """,
                    (product_id, ingredient_id, _field(row, "Strength"), raw),
                )
                counts["ingredients"] += 1
            counts["products"] += 1
    return counts
