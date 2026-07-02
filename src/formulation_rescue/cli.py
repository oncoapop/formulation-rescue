"""Command-line interface for the FDA formulation-rescue pipeline."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .database import DEFAULT_DB, initialize_database, score_phase1
from .export import DEFAULT_CSV, DEFAULT_REPORT, export_phase1
from .fda import (
    DEFAULT_DRUGS_FDA_ARCHIVE,
    DEFAULT_ORANGE_BOOK_ARCHIVE,
    download_orange_book,
    ingest_drugs_fda,
    ingest_orange_book,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="formulation-rescue")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db")
    download = subparsers.add_parser("download-orange-book")
    download.add_argument("--output", type=Path, default=DEFAULT_ORANGE_BOOK_ARCHIVE)
    orange = subparsers.add_parser("ingest-orange-book")
    orange.add_argument("--source", type=Path, default=DEFAULT_ORANGE_BOOK_ARCHIVE)
    drugs = subparsers.add_parser("ingest-drugs-fda")
    drugs.add_argument("--source", type=Path, default=DEFAULT_DRUGS_FDA_ARCHIVE)
    score = subparsers.add_parser("score-phase1")
    score.add_argument("--as-of", type=date.fromisoformat)
    export = subparsers.add_parser("export-phase1-csv")
    export.add_argument("--output", type=Path, default=DEFAULT_CSV)
    export.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    phase1 = subparsers.add_parser("run-phase1")
    phase1.add_argument(
        "--orange-book", type=Path, default=DEFAULT_ORANGE_BOOK_ARCHIVE
    )
    phase1.add_argument(
        "--drugs-fda", type=Path, default=DEFAULT_DRUGS_FDA_ARCHIVE
    )
    phase1.add_argument("--as-of", type=date.fromisoformat)
    phase1.add_argument("--output", type=Path, default=DEFAULT_CSV)
    phase1.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def run(args: argparse.Namespace) -> int:
    if args.command == "init-db":
        initialize_database(args.db)
        print(f"Initialized {args.db}")
        return 0
    if args.command == "download-orange-book":
        path = download_orange_book(args.output)
        print(f"Downloaded Orange Book to {path}")
        return 0
    if args.command == "ingest-orange-book":
        counts = ingest_orange_book(args.source, args.db)
        print("Ingested Orange Book: " + _format_counts(counts))
        return 0
    if args.command == "ingest-drugs-fda":
        counts = ingest_drugs_fda(args.source, args.db)
        print("Ingested Drugs@FDA: " + _format_counts(counts))
        return 0
    if args.command == "score-phase1":
        count = score_phase1(args.db, args.as_of)
        print(f"Scored {count} candidates")
        return 0
    if args.command == "export-phase1-csv":
        count = export_phase1(args.db, args.output, args.report)
        print(f"Exported {count} candidates to {args.output}")
        return 0
    if args.command == "run-phase1":
        initialize_database(args.db)
        if not args.orange_book.exists():
            download_orange_book(args.orange_book)
        orange_counts = ingest_orange_book(args.orange_book, args.db)
        drugs_counts = ingest_drugs_fda(args.drugs_fda, args.db)
        count = score_phase1(args.db, args.as_of)
        export_phase1(args.db, args.output, args.report)
        print(
            f"Pipeline complete: {_format_counts(orange_counts)} Orange Book; "
            f"{_format_counts(drugs_counts)} Drugs@FDA; {count} candidates"
        )
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run(parser.parse_args(argv))


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{name}={count}" for name, count in counts.items())


if __name__ == "__main__":
    raise SystemExit(main())
