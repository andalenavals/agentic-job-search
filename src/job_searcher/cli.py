from __future__ import annotations

import argparse
import sys
from pathlib import Path

from job_searcher.debugging import (
    debug_report_to_flat_markdown,
    debug_report_to_markdown,
    debug_sources,
    flatten_debug_jobs,
)
from job_searcher.emailing import build_digest_email, email_settings_from_env, send_email
from job_searcher.exporters import to_csv, to_markdown
from job_searcher.matching import ProfileMatcher
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
        profile = load_profile(args.profile, args.profile_file)
        profile_matcher = (
            ProfileMatcher(
                profile,
                ollama_model=None if args.no_llm_match else args.ollama_model,
                timeout=args.match_timeout,
            )
            if profile
            else None
        )
        results = debug_sources(
            sources,
            query,
            per_source_limit=args.debug_limit,
            timeout=args.debug_timeout,
        )
        flat_rows = flatten_debug_jobs(results, profile_matcher)
        if profile_matcher:
            rendered = debug_report_to_flat_markdown(
                results,
                title=args.title,
                per_source_limit=args.debug_limit,
                profile_matcher=profile_matcher,
                flat_rows=flat_rows,
            )
        else:
            rendered = debug_report_to_markdown(results)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        if args.email_to:
            settings = email_settings_from_env(from_addr=args.email_from)
            message = build_digest_email(
                flat_rows,
                query_title=args.title,
                to_addr=args.email_to,
                from_addr=settings.from_addr,
                from_name=settings.from_name,
                subject=args.email_subject,
                limit=args.email_top,
                sort_by=args.email_sort,
            )
            send_email(message, settings)
            print(f"Sent top {args.email_top} job digest to {args.email_to}", file=sys.stderr)
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
        "--profile",
        help="Candidate profile text used to rank debug report jobs by fit.",
    )
    parser.add_argument(
        "--profile-file",
        help="Path to a text file containing the candidate profile used to rank debug report jobs by fit.",
    )
    parser.add_argument(
        "--ollama-model",
        default="deepseek-r1:latest",
        help="Ollama model for LLM job/profile matching in --debug-links mode.",
    )
    parser.add_argument(
        "--no-llm-match",
        action="store_true",
        help="Skip Ollama matching and only compute the simple semantic match.",
    )
    parser.add_argument(
        "--match-timeout",
        type=int,
        default=30,
        help="Seconds to wait for each Ollama match request.",
    )
    parser.add_argument("--email-to", help="Send a top job digest to this email address in --debug-links mode.")
    parser.add_argument("--email-from", help="Email sender address. Defaults to JOB_SEARCH_EMAIL_FROM.")
    parser.add_argument("--email-subject", help="Custom subject for the job digest email.")
    parser.add_argument(
        "--email-top",
        type=int,
        default=5,
        help="Number of jobs to include in the email digest.",
    )
    parser.add_argument(
        "--email-sort",
        choices=("match", "newest", "source"),
        default="match",
        help="How to choose jobs for the email digest.",
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


def load_profile(profile: str | None, profile_file: str | None) -> str:
    values = []
    if profile:
        values.append(profile)
    if profile_file:
        values.append(Path(profile_file).read_text(encoding="utf-8"))
    return "\n\n".join(value.strip() for value in values if value.strip())


if __name__ == "__main__":
    raise SystemExit(main())
