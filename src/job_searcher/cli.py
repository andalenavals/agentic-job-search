from __future__ import annotations

import argparse
import sys
from pathlib import Path

from job_searcher.exporters import to_csv, to_markdown
from job_searcher.models import SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.search import collect_jobs
from job_searcher.sources import DEFAULT_SOURCE_NAMES, DEFAULT_SOURCES, PLACEHOLDER_SOURCES, build_sources


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source_names = args.source or list(DEFAULT_SOURCE_NAMES)
    try:
        sources = build_sources(source_names, tuple(args.greenhouse), tuple(args.lever))
    except ValueError as exc:
        parser.error(str(exc))

    query = SearchQuery(
        title=args.title,
        location=args.location,
        remote=args.remote,
        limit=args.limit,
        include_unverified=args.include_unverified,
        greenhouse_companies=tuple(args.greenhouse),
        lever_companies=tuple(args.lever),
    )
    report = SearchReport()
    jobs = collect_jobs(sources, query, report)
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if not jobs and report.filtered_unverified:
        print(
            "warning: "
            f"{report.filtered_unverified} matching posting(s) were found, but their links "
            "did not look like official company application pages. "
            "Use --include-unverified to inspect them.",
            file=sys.stderr,
        )
    rendered = to_csv(jobs) if args.format == "csv" else to_markdown(jobs)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-job-search",
        description="Collect likely official application links for job searches.",
    )
    parser.add_argument("--title", required=True, help="Job title or title keywords.")
    parser.add_argument("--location", help="Location keyword, for example Berlin or Remote.")
    parser.add_argument("--remote", action="store_true", help="Prefer remote roles.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum number of results.")
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Include source links that do not look like official company application pages.",
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted([*DEFAULT_SOURCES, *PLACEHOLDER_SOURCES]),
        help="Source to search. Can be passed multiple times.",
    )
    parser.add_argument(
        "--greenhouse",
        action="append",
        default=[],
        help="Greenhouse company board token, for example stripe.",
    )
    parser.add_argument(
        "--lever",
        action="append",
        default=[],
        help="Lever company board token.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "csv"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument("--output", help="Write output to a file instead of stdout.")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
