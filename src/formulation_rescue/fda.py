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

_REQUIRED_HEADERS = {
    "products.txt:~": {
        "Ingredient",
        "DF;Route",
        "Appl_Type",
        "Appl_No",
        "Product_No",
        "Strength",
    },
    "patent.txt:~": {
        "Appl_Type",
        "Appl_No",
        "Product_No",
        "Patent_No",
        "Patent_Expire_Date_Text",
    },
    "exclusivity.txt:~": {
        "Appl_Type",
        "Appl_No",
        "Product_No",
        "Exclusivity_Code",
        "Exclusivity_Date",
    },
    "applications.txt:\t": {"ApplNo", "ApplType", "SponsorName"},
    "products.txt:\t": {
        "ApplNo",
        "ProductNo",
        "Form",
        "Strength",
        "DrugName",
        "ActiveIngredient",
    },
    "marketingstatus.txt:\t": {"MarketingStatusID", "ApplNo", "ProductNo"},
    "marketingstatus_lookup.txt:\t": {
        "MarketingStatusID",
        "MarketingStatusDescription",
    },
}

PARENTERAL_ROUTES = {
    "intravenous",
    "intramuscular",
    "subcutaneous",
    "intradermal",
    "intra-arterial",
    "intrathecal",
    "epidural",
    "intraocular",
    "intravitreal",
    "intra-articular",
    "intraperitoneal",
    "injectable",
    "infusion",
    "parenteral",
}

_ROUTE_ALIASES = {
    "iv": "intravenous",
    "i.v.": "intravenous",
    "intravenous": "intravenous",
    "im": "intramuscular",
    "i.m.": "intramuscular",
    "intramuscular": "intramuscular",
    "intra muscular": "intramuscular",
    "sc": "subcutaneous",
    "sq": "subcutaneous",
    "s.c.": "subcutaneous",
    "subcutaneous": "subcutaneous",
    "sub cutaneous": "subcutaneous",
    "id": "intradermal",
    "intradermal": "intradermal",
    "intra-arterial": "intra-arterial",
    "intraarterial": "intra-arterial",
    "intrathecal": "intrathecal",
    "epidural": "epidural",
    "intraocular": "intraocular",
    "intravitreal": "intravitreal",
    "intra-articular": "intra-articular",
    "intraarticular": "intra-articular",
    "intraperitoneal": "intraperitoneal",
    "injection": "injectable",
    "injectable": "injectable",
    "infusion": "infusion",
    "parenteral": "parenteral",
}

_KNOWN_NONPARENTERAL_ROUTES = {
    "auricular (otic)",
    "buccal",
    "cutaneous",
    "dental",
    "endotracheal",
    "enteral",
    "gingival",
    "inhalation",
    "implantation",
    "intra-anal",
    "intracameral",
    "intracavitary",
    "intracavernosal",
    "intracranial",
    "intralesional",
    "intralymphatic",
    "intranasal",
    "intrapleural",
    "intratracheal",
    "intrauterine",
    "intraosseous",
    "intravesical",
    "intravesicular",
    "irrigation",
    "iontophoresis",
    "nasal",
    "ophthalmic",
    "oral",
    "oropharyngeal",
    "otic",
    "periodontal",
    "perfusion",
    "pyelocalyceal",
    "rectal",
    "sublingual",
    "topical",
    "transdermal",
    "transmucosal",
    "urethral",
    "ureteral",
    "vaginal",
    "biliary",
    "endocervical",
    "infiltration",
    "interstitial",
}

_ROUTE_COMPOSITES = {
    "im-iv": ["intramuscular", "intravenous"],
    "iv (infusion)": ["intravenous", "infusion"],
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
        expected = _REQUIRED_HEADERS.get(f"{filename.lower()}:{delimiter}", set())
        missing = expected - {name.strip() for name in reader.fieldnames}
        if missing:
            raise ValueError(
                f"{filename} is missing required columns: "
                + ", ".join(sorted(missing))
            )
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


def _clean_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def canonicalize_routes(value: str) -> tuple[list[str], bool, bool]:
    """Return canonical routes, whether any is parenteral, and unknown evidence."""
    if not value.strip():
        return [], False, True
    canonical: list[str] = []
    unknown = False
    for raw_token in value.split(","):
        token = _clean_token(raw_token)
        composite = _ROUTE_COMPOSITES.get(token)
        if composite:
            for mapped in composite:
                if mapped not in canonical:
                    canonical.append(mapped)
            continue
        mapped = _ROUTE_ALIASES.get(token)
        if mapped is None and re.fullmatch(r"oral-\d+", token):
            mapped = "oral"
        if mapped is None and token == "periarticular":
            mapped = "intra-articular"
        if mapped is None and token in _KNOWN_NONPARENTERAL_ROUTES:
            mapped = token
        if mapped is None:
            unknown = True
            continue
        if mapped not in canonical:
            canonical.append(mapped)
    return canonical, any(route in PARENTERAL_ROUTES for route in canonical), unknown


def canonicalize_dosage_form(value: str) -> tuple[str, bool]:
    token = _clean_token(value).replace(" :", ":")
    if not token or token in {"unknown", "n/a", "na"}:
        return "", True
    return token, False


def _split_form_route(value: str) -> tuple[str, str, bool]:
    if value.count(";") != 1:
        return value.strip(), "", True
    dosage_form, route = value.split(";", 1)
    return dosage_form.strip(), route.strip(), False


def _ingredient_strength_pairs(
    active_ingredient: str, strength: str
) -> tuple[list[tuple[str, str | None]], str]:
    ingredients = _split_ingredients(active_ingredient)
    if not ingredients:
        return [], "unknown"
    normalized = [" ".join(ingredient.split()).casefold() for ingredient in ingredients]
    if len(set(normalized)) != len(normalized):
        unique: dict[str, str] = {}
        for key, ingredient in zip(normalized, ingredients):
            unique.setdefault(key, ingredient)
        return [(ingredient, None) for ingredient in unique.values()], (
            "ambiguous_multi_ingredient_strength"
        )
    if not strength.strip():
        return [(ingredient, None) for ingredient in ingredients], "missing_strength"
    if len(ingredients) == 1:
        return [(ingredients[0], strength.strip())], "exact_single_ingredient"
    strengths = [part.strip() for part in strength.split(";")]
    if len(strengths) == len(ingredients) and all(strengths):
        return list(zip(ingredients, strengths)), "exact_multi_ingredient"
    return [(ingredient, None) for ingredient in ingredients], (
        "ambiguous_multi_ingredient_strength"
    )


def _marketing_status_class(status: str) -> str:
    normalized = _clean_token(status)
    if normalized in {"rx", "prescription", "otc", "over-the-counter"}:
        return "active"
    if normalized in {"discn", "discontinued"}:
        return "discontinued"
    if "tentative" in normalized or "manufacturing use" in normalized:
        return "tentative_or_nonmarketed"
    return "unknown"


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
            is_discontinued = excluded.is_discontinued,
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


def _record_product_observation(
    connection: sqlite3.Connection,
    *,
    product_id: int,
    source_file_id: int,
    source_name: str,
    application_type: str,
    sponsor_name: str,
    dosage_form_raw: str,
    route_raw: str,
    marketing_status: str,
    raw_active_ingredient: str,
    raw_strength: str,
    mapping_quality: str,
    raw_json: str,
    malformed_form_route: bool = False,
) -> None:
    routes, parenteral, unknown_route = canonicalize_routes(route_raw)
    canonical_form, unknown_form = canonicalize_dosage_form(dosage_form_raw)
    now = datetime.now(timezone.utc).isoformat()
    connection.execute(
        """
        INSERT INTO product_observations (
            product_id, source_file_id, source_name, active_in_latest_snapshot,
            application_type, sponsor_name, dosage_form_raw, route_raw,
            canonical_dosage_form, canonical_route, parenteral_route_signal,
            unknown_dosage_form, unknown_route, marketing_status,
            marketing_status_class, raw_active_ingredient, raw_strength,
            mapping_quality, observed_at, raw_json
        ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_id, source_file_id) DO UPDATE SET
            active_in_latest_snapshot = 1,
            application_type = excluded.application_type,
            sponsor_name = excluded.sponsor_name,
            dosage_form_raw = excluded.dosage_form_raw,
            route_raw = excluded.route_raw,
            canonical_dosage_form = excluded.canonical_dosage_form,
            canonical_route = excluded.canonical_route,
            parenteral_route_signal = excluded.parenteral_route_signal,
            unknown_dosage_form = excluded.unknown_dosage_form,
            unknown_route = excluded.unknown_route,
            marketing_status = excluded.marketing_status,
            marketing_status_class = excluded.marketing_status_class,
            raw_active_ingredient = excluded.raw_active_ingredient,
            raw_strength = excluded.raw_strength,
            mapping_quality = excluded.mapping_quality,
            observed_at = excluded.observed_at,
            raw_json = excluded.raw_json
        """,
        (
            product_id,
            source_file_id,
            source_name,
            application_type,
            sponsor_name,
            dosage_form_raw,
            route_raw,
            canonical_form,
            "; ".join(routes),
            int(parenteral),
            int(unknown_form),
            int(unknown_route or malformed_form_route),
            marketing_status,
            _marketing_status_class(marketing_status),
            raw_active_ingredient,
            raw_strength,
            mapping_quality,
            now,
            raw_json,
        ),
    )


def _replace_product_ingredients(
    connection: sqlite3.Connection,
    product_id: int,
    raw_active_ingredient: str,
    raw_strength: str,
    raw_json: str,
) -> tuple[int, str]:
    pairs, mapping_quality = _ingredient_strength_pairs(
        raw_active_ingredient, raw_strength
    )
    connection.execute(
        "DELETE FROM product_ingredients WHERE product_id = ?", (product_id,)
    )
    for ingredient, strength in pairs:
        ingredient_id = _ingredient_id(connection, ingredient, raw_json)
        connection.execute(
            """
            INSERT INTO product_ingredients (
                product_id, ingredient_id, strength, raw_active_ingredient,
                raw_strength, mapping_quality, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                ingredient_id,
                strength,
                raw_active_ingredient,
                raw_strength,
                mapping_quality,
                raw_json,
            ),
        )
    return len(pairs), mapping_quality


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
        connection.execute(
            """
            UPDATE product_observations SET active_in_latest_snapshot = 0
            WHERE source_name = 'FDA Orange Book'
            """
        )
        connection.execute("UPDATE patents SET ip_active_in_latest_snapshot = 0")
        connection.execute("UPDATE exclusivities SET ip_active_in_latest_snapshot = 0")
        for row in _rows(source, "products.txt", "~"):
            raw = json.dumps(row, ensure_ascii=False, sort_keys=True)
            application = _application_number(
                _field(row, "Appl_No"), _field(row, "Appl_Type")
            )
            form_route = _field(row, "DF;Route")
            dosage_form, route, malformed_form_route = _split_form_route(form_route)
            raw_ingredient = _field(row, "Ingredient")
            raw_strength = _field(row, "Strength")
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
            ingredient_count, mapping_quality = _replace_product_ingredients(
                connection, product_id, raw_ingredient, raw_strength, raw
            )
            counts["ingredients"] += ingredient_count
            _record_product_observation(
                connection,
                product_id=product_id,
                source_file_id=source_id,
                source_name="FDA Orange Book",
                application_type=_field(row, "Appl_Type"),
                sponsor_name=_field(row, "Applicant_Full_Name", "Applicant"),
                dosage_form_raw=dosage_form,
                route_raw=route,
                marketing_status=_field(row, "Type"),
                raw_active_ingredient=raw_ingredient,
                raw_strength=raw_strength,
                mapping_quality=mapping_quality,
                raw_json=raw,
                malformed_form_route=malformed_form_route,
            )
            counts["products"] += 1

        product_ids = {
            (row["application_number"], row["product_number"]): row["id"]
            for row in connection.execute(
                "SELECT id, application_number, product_number FROM products"
            )
        }
        observed_at = datetime.now(timezone.utc).isoformat()
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
                    ip_active_in_latest_snapshot, ip_first_seen_at, ip_last_seen_at,
                    delist_requested_signal, pediatric_extension_signal,
                    source_file_id, raw_json
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, patent_number, use_code) DO UPDATE SET
                    patent_expiry = excluded.patent_expiry,
                    ip_active_in_latest_snapshot = 1,
                    ip_first_seen_at = COALESCE(
                        patents.ip_first_seen_at, excluded.ip_first_seen_at
                    ),
                    ip_last_seen_at = excluded.ip_last_seen_at,
                    delist_requested_signal = excluded.delist_requested_signal,
                    pediatric_extension_signal =
                        excluded.pediatric_extension_signal,
                    source_file_id = excluded.source_file_id,
                    raw_json = excluded.raw_json
                """,
                (
                    product_id,
                    _field(row, "Patent_No"),
                    _iso_date(_field(row, "Patent_Expire_Date_Text", "Patent_Expire_Date")),
                    _field(row, "Patent_Use_Code"),
                    observed_at,
                    observed_at,
                    int(_field(row, "Delist_Flag").upper() == "Y"),
                    int("PED" in _field(row, "Patent_No").upper()),
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
                    ip_active_in_latest_snapshot, ip_first_seen_at, ip_last_seen_at,
                    pediatric_extension_signal, source_file_id, raw_json
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(
                    product_id, exclusivity_code, exclusivity_expiry
                ) DO UPDATE SET
                    ip_active_in_latest_snapshot = 1,
                    ip_first_seen_at = COALESCE(
                        exclusivities.ip_first_seen_at, excluded.ip_first_seen_at
                    ),
                    ip_last_seen_at = excluded.ip_last_seen_at,
                    pediatric_extension_signal =
                        excluded.pediatric_extension_signal,
                    source_file_id = excluded.source_file_id,
                    raw_json = excluded.raw_json
                """,
                (
                    product_id,
                    _field(row, "Exclusivity_Code"),
                    _iso_date(_field(row, "Exclusivity_Date")),
                    observed_at,
                    observed_at,
                    int(_field(row, "Exclusivity_Code").upper() == "PED"),
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
        connection.execute(
            """
            UPDATE product_observations SET active_in_latest_snapshot = 0
            WHERE source_name = 'Drugs@FDA'
            """
        )
        for row in _rows(source, "Products.txt", "\t"):
            application_row = applications.get(_field(row, "ApplNo"), {})
            application_type = _field(application_row, "ApplType")
            if not application_type:
                suffix = _field(row, "ApplNo").zfill(6)
                product_number = _field(row, "ProductNo")
                candidates = connection.execute(
                    """
                    SELECT DISTINCT application_number
                    FROM products
                    WHERE application_number LIKE ?
                      AND product_number = ?
                      AND application_number NOT LIKE 'FDA%'
                    """,
                    (f"%{suffix}", product_number),
                ).fetchall()
                if len(candidates) == 1:
                    application_type = re.sub(
                        r"\d+$", "", candidates[0]["application_number"]
                    )
            application = _application_number(
                _field(row, "ApplNo"), application_type
            )
            form_route = _field(row, "Form")
            dosage_form, route, malformed_form_route = _split_form_route(form_route)
            status = statuses.get(
                (_field(row, "ApplNo"), _field(row, "ProductNo")), ""
            )
            combined_raw = {
                "product": row,
                "application": application_row,
                "marketing_status": status,
            }
            raw = json.dumps(combined_raw, ensure_ascii=False, sort_keys=True)
            raw_ingredient = _field(row, "ActiveIngredient")
            raw_strength = _field(row, "Strength")
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
            ingredient_count, mapping_quality = _replace_product_ingredients(
                connection, product_id, raw_ingredient, raw_strength, raw
            )
            counts["ingredients"] += ingredient_count
            _record_product_observation(
                connection,
                product_id=product_id,
                source_file_id=source_id,
                source_name="Drugs@FDA",
                application_type=application_type,
                sponsor_name=_field(application_row, "SponsorName"),
                dosage_form_raw=dosage_form,
                route_raw=route,
                marketing_status=status,
                raw_active_ingredient=raw_ingredient,
                raw_strength=raw_strength,
                mapping_quality=mapping_quality,
                raw_json=raw,
                malformed_form_route=malformed_form_route,
            )
            counts["products"] += 1
        connection.execute(
            """
            DELETE FROM products
            WHERE NOT EXISTS (
                SELECT 1 FROM product_observations po
                WHERE po.product_id = products.id
            )
            """
        )
        connection.execute(
            """
            DELETE FROM ingredients
            WHERE NOT EXISTS (
                SELECT 1 FROM product_ingredients pi
                WHERE pi.ingredient_id = ingredients.id
            )
            """
        )
    return counts
