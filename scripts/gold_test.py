from __future__ import annotations

import argparse
from pathlib import Path

from job_searcher.debugging import debug_report_to_flat_markdown, debug_sources, flatten_debug_jobs
from job_searcher.emailing import build_digest_email, email_settings_from_env, send_email
from job_searcher.matching import ProfileMatcher
from job_searcher.models import SearchQuery
from job_searcher.sources import DEFAULT_SOURCES, PLACEHOLDER_SOURCES, build_sources


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a live gold test across all selectable job sources."
    )
    parser.add_argument("--title", default="Data", help="Job title query.")
    parser.add_argument(
        "--per-source-limit",
        type=int,
        default=5,
        help="Number of links to collect and verify per source.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=8,
        help="Seconds to wait while verifying each final link.",
    )
    parser.add_argument(
        "--output",
        default="reports/gold-test-data.md",
        help="Markdown report path.",
    )
    parser.add_argument(
        "--profile",
        help="Candidate profile text used to rank jobs by fit.",
    )
    parser.add_argument(
        "--profile-file",
        help="Path to a text file containing the candidate profile used to rank jobs by fit.",
    )
    parser.add_argument(
        "--ollama-model",
        default="deepseek-r1:latest",
        help="Ollama model for LLM job/profile matching. Use --no-llm-match to skip it.",
    )
    parser.add_argument(
        "--no-llm-match",
        action="store_true",
        help="Skip the Ollama LLM match and only compute the simple semantic score.",
    )
    parser.add_argument(
        "--match-timeout",
        type=int,
        default=30,
        help="Seconds to wait for each Ollama match request.",
    )
    parser.add_argument("--email-to", help="Send the top job digest to this email address.")
    parser.add_argument("--email-from", help="Email sender address. Defaults to JOB_SEARCH_EMAIL_FROM.")
    parser.add_argument(
        "--email-subject",
        help="Custom subject for the job digest email.",
    )
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
    args = parser.parse_args()

    source_names = sorted([*DEFAULT_SOURCES, *PLACEHOLDER_SOURCES])
    sources = build_sources(source_names, (), ())
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
    query = SearchQuery(
        title=args.title,
        limit=args.per_source_limit,
        include_unverified=True,
    )
    results = debug_sources(
        sources,
        query,
        per_source_limit=args.per_source_limit,
        timeout=args.timeout,
    )
    flat_rows = flatten_debug_jobs(results, profile_matcher)
    report = debug_report_to_flat_markdown(
        results,
        title=args.title,
        per_source_limit=args.per_source_limit,
        profile_matcher=profile_matcher,
        flat_rows=flat_rows,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote gold test report to {output}")
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
        print(f"Sent top {args.email_top} job digest to {args.email_to}")
    return 0


def load_profile(profile: str | None, profile_file: str | None) -> str:
    values = []
    if profile:
        values.append(profile)
    if profile_file:
        values.append(Path(profile_file).read_text(encoding="utf-8"))
    return "\n\n".join(value.strip() for value in values if value.strip())


if __name__ == "__main__":
    raise SystemExit(main())
