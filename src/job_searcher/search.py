from __future__ import annotations

from collections.abc import Iterable

from job_searcher.models import JobPosting, SearchQuery
from job_searcher.official_links import is_likely_official_application
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


def collect_jobs(
    sources: Iterable[JobSource], query: SearchQuery, report: SearchReport | None = None
) -> list[JobPosting]:
    seen_urls: set[str] = set()
    seen_positions: set[tuple[str, str, str]] = set()
    results: list[JobPosting] = []
    for source in sources:
        for job in source.search(query, report):
            if report:
                report.seen += 1
            if not job.best_url:
                if report:
                    report.filtered_duplicates += 1
                continue
            url_key = normalize_url(job.best_url)
            if url_key in seen_urls:
                if report:
                    report.filtered_duplicate_links += 1
                    report.filtered_duplicates += 1
                continue
            position_key = duplicate_position_key(job)
            if position_key and position_key in seen_positions:
                if report:
                    report.filtered_duplicate_positions += 1
                    report.filtered_duplicates += 1
                continue
            if (
                not query.include_unverified
                and not is_likely_official_application(job.best_url, job.company)
            ):
                if report:
                    report.filtered_unverified += 1
                continue
            seen_urls.add(url_key)
            if position_key:
                seen_positions.add(position_key)
            results.append(job)
            if report:
                report.accepted += 1
    return sort_jobs(results)[: query.limit]


def sort_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    return sorted(
        jobs,
        key=lambda job: (
            job.published_at is None,
            -(job.published_at.timestamp() if job.published_at else 0),
            job.company.lower(),
            job.title.lower(),
        ),
    )


def duplicate_position_key(job: JobPosting) -> tuple[str, str, str] | None:
    title = normalize_position_text(job.title)
    company = normalize_position_text(job.company)
    location = normalize_position_text(job.location or "")
    if not title or not company:
        return None
    return (title, company, location)


def normalize_position_text(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return " ".join(normalized.split())


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/")
