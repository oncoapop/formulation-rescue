"""Command-line interface for the FDA formulation-rescue pipeline."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .database import DEFAULT_DB, PROJECT_ROOT, initialize_database, score_phase1
from .dailymed import (
    DEFAULT_DAILYMED_RAW,
    DEFAULT_ENRICHED_CSV,
    DEFAULT_PHASE3_REPORT,
    DEFAULT_SCIENCE_REVIEW_CSV,
    DEFAULT_SIGNALS_CSV,
    download_dailymed_labels,
    export_scientific_rescue_signals,
    ingest_dailymed_labels,
    score_label_burden,
)
from .export import DEFAULT_CSV, DEFAULT_REPORT, export_phase1
from .fda import (
    DEFAULT_DRUGS_FDA_ARCHIVE,
    DEFAULT_ORANGE_BOOK_ARCHIVE,
    download_orange_book,
    ingest_drugs_fda,
    ingest_orange_book,
)
from .scientific_review import (
    DEFAULT_REVIEW_CSV,
    DEFAULT_REVIEW_REPORT,
    build_top100_scientific_review,
)
from .review_package import build_review_package
from .rescueability import (
    DEFAULT_QUEUES_REPORT,
    DEFAULT_RESCUEABILITY_CSV,
    DEFAULT_RESCUEABILITY_REPORT,
    build_rescueability_review,
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
    dailymed_download = subparsers.add_parser("download-dailymed-labels")
    dailymed_download.add_argument(
        "--input", type=Path, default=DEFAULT_SCIENCE_REVIEW_CSV
    )
    dailymed_download.add_argument(
        "--raw-dir", type=Path, default=DEFAULT_DAILYMED_RAW
    )
    dailymed_download.add_argument("--limit", type=int)
    dailymed_download.add_argument("--refresh", action="store_true")
    dailymed_download.add_argument("--delay", type=float, default=0.1)
    dailymed_ingest = subparsers.add_parser("ingest-dailymed-labels")
    dailymed_ingest.add_argument(
        "--raw-dir", type=Path, default=DEFAULT_DAILYMED_RAW
    )
    subparsers.add_parser("score-label-burden")
    scientific_export = subparsers.add_parser(
        "export-scientific-rescue-signals"
    )
    scientific_export.add_argument(
        "--enriched-output", type=Path, default=DEFAULT_ENRICHED_CSV
    )
    scientific_export.add_argument(
        "--signals-output", type=Path, default=DEFAULT_SIGNALS_CSV
    )
    scientific_export.add_argument(
        "--report", type=Path, default=DEFAULT_PHASE3_REPORT
    )
    scientific_export.add_argument("--limit", type=int, default=100)
    review = subparsers.add_parser("review-top-scientific-signals")
    review.add_argument("--input", type=Path, default=DEFAULT_SIGNALS_CSV)
    review.add_argument("--output", type=Path, default=DEFAULT_REVIEW_CSV)
    review.add_argument("--report", type=Path, default=DEFAULT_REVIEW_REPORT)
    review.add_argument("--raw-dir", type=Path, default=DEFAULT_DAILYMED_RAW)
    package = subparsers.add_parser("build-review-package")
    package.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    package.add_argument(
        "--export-root", type=Path, default=PROJECT_ROOT / "exports"
    )
    rescueability = subparsers.add_parser("rank-rescueability")
    rescueability.add_argument("--input", type=Path, default=DEFAULT_REVIEW_CSV)
    rescueability.add_argument("--output", type=Path, default=DEFAULT_RESCUEABILITY_CSV)
    rescueability.add_argument("--report", type=Path, default=DEFAULT_RESCUEABILITY_REPORT)
    rescueability.add_argument("--queues-report", type=Path, default=DEFAULT_QUEUES_REPORT)
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
    if args.command == "download-dailymed-labels":
        counts = download_dailymed_labels(
            args.input,
            args.raw_dir,
            limit=args.limit,
            refresh=args.refresh,
            delay_seconds=args.delay,
        )
        print("DailyMed download: " + _format_counts(counts))
        return 0
    if args.command == "ingest-dailymed-labels":
        counts = ingest_dailymed_labels(args.raw_dir, args.db)
        print("DailyMed ingestion: " + _format_counts(counts))
        return 0
    if args.command == "score-label-burden":
        count = score_label_burden(args.db)
        print(f"Scored DailyMed burden for {count} candidates")
        return 0
    if args.command == "export-scientific-rescue-signals":
        counts = export_scientific_rescue_signals(
            args.db,
            args.enriched_output,
            args.signals_output,
            args.report,
            limit=args.limit,
        )
        print("Scientific rescue export: " + _format_counts(counts))
        return 0
    if args.command == "review-top-scientific-signals":
        rows = build_top100_scientific_review(
            args.input, args.output, args.report, args.raw_dir
        )
        print(f"Reviewed {len(rows)} scientific rescue signals")
        return 0
    if args.command == "build-review-package":
        result = build_review_package(args.review_csv, args.export_root)
        print(
            f"Review package: files={result['file_count']}, "
            f"candidate_packets={result['candidate_packets']}, "
            f"path={result['package_path']}"
        )
        return 0
    if args.command == "rank-rescueability":
        rows = build_rescueability_review(
            args.input, args.output, args.report, args.queues_report
        )
        print(f"Ranked rescueability for {len(rows)} candidates")
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run(parser.parse_args(argv))


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{name}={count}" for name, count in counts.items())


if __name__ == "__main__":
    raise SystemExit(main())
