from __future__ import annotations

import argparse
import sys
from pathlib import Path

from job_searcher.debugging import debug_report_to_markdown, debug_sources
from job_searcher.exporters import to_csv, to_markdown
from job_searcher.models import SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.search import collect_jobs
from job_searcher.sources import DEFAULT_SOURCE_NAMES, DEFAULT_SOURCES, PLACEHOLDER_SOURCES, build_sources

ALL_SOURCES = "all"
ALL_LOCATIONS = "all"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source_names = normalize_source_names(args.source)
    location = normalize_location(args.location)
    try:
        sources = build_sources(
            source_names,
            tuple(args.greenhouse),
            tuple(args.lever),
            tuple(args.ashby),
            tuple(args.personio),
            tuple(args.smartrecruiters),
            tuple(args.workday),
        )
    except ValueError as exc:
        parser.error(str(exc))

    query = SearchQuery(
        title=args.title,
        location=location,
        remote=args.remote,
        limit=args.limit,
        include_unverified=args.include_unverified or args.debug_links,
        greenhouse_companies=tuple(args.greenhouse),
        lever_companies=tuple(args.lever),
        ashby_companies=tuple(args.ashby),
        personio_companies=tuple(args.personio),
        smartrecruiters_companies=tuple(args.smartrecruiters),
        workday_sites=tuple(args.workday),
    )
    if args.debug_links:
        results = debug_sources(
            sources,
            query,
            per_source_limit=args.debug_limit,
            timeout=args.debug_timeout,
        )
        rendered = debug_report_to_markdown(results)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0

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
    parser.add_argument(
        "--location",
        help="Location keyword, for example Berlin or Remote. Use 'all' for no location filter.",
    )
    parser.add_argument("--remote", action="store_true", help="Prefer remote roles.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum number of results.")
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Include source links that do not look like official company application pages.",
    )
    parser.add_argument(
        "--debug-links",
        action="store_true",
        help="Search each source separately and verify the first links by fetching them.",
    )
    parser.add_argument(
        "--debug-limit",
        type=int,
        default=5,
        help="Number of links to verify per source in --debug-links mode.",
    )
    parser.add_argument(
        "--debug-timeout",
        type=int,
        default=10,
        help="Seconds to wait while verifying each debug link.",
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted([ALL_SOURCES, *DEFAULT_SOURCES, *PLACEHOLDER_SOURCES]),
        help="Source to search. Can be passed multiple times. Use 'all' for every selectable source.",
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
        "--ashby",
        action="append",
        default=[],
        help="Ashby job board token, for example a company slug from jobs.ashbyhq.com.",
    )
    parser.add_argument(
        "--personio",
        action="append",
        default=[],
        help="Personio company token, for example acme from acme.jobs.personio.de.",
    )
    parser.add_argument(
        "--smartrecruiters",
        action="append",
        default=[],
        help="SmartRecruiters company token.",
    )
    parser.add_argument(
        "--workday",
        action="append",
        default=[],
        help="Full Workday candidate site URL.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "csv"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument("--output", help="Write output to a file instead of stdout.")
    return parser


def normalize_source_names(source_names: list[str] | None) -> list[str]:
    if not source_names:
        return list(DEFAULT_SOURCE_NAMES)
    if ALL_SOURCES in source_names:
        return sorted([*DEFAULT_SOURCES, *PLACEHOLDER_SOURCES])
    return source_names


def normalize_location(location: str | None) -> str | None:
    if location and location.strip().lower() == ALL_LOCATIONS:
        return None
    return location


if __name__ == "__main__":
    raise SystemExit(main())
