from __future__ import annotations

import argparse
from pathlib import Path

from job_searcher.debugging import debug_report_to_flat_markdown, debug_sources
from job_searcher.models import SearchQuery
from job_searcher.sources import DEFAULT_SOURCES, PLACEHOLDER_SOURCES, build_sources


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a live cold test across all selectable job sources."
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
        default="reports/cold-test-data.md",
        help="Markdown report path.",
    )
    args = parser.parse_args()

    source_names = sorted([*DEFAULT_SOURCES, *PLACEHOLDER_SOURCES])
    sources = build_sources(source_names, (), ())
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
    report = debug_report_to_flat_markdown(
        results,
        title=args.title,
        per_source_limit=args.per_source_limit,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote cold test report to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
