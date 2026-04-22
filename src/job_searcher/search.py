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
    results: list[JobPosting] = []
    for source in sources:
        for job in source.search(query, report):
            if not job.best_url or job.best_url in seen_urls:
                continue
            if (
                not query.include_unverified
                and not is_likely_official_application(job.best_url, job.company)
            ):
                continue
            seen_urls.add(job.best_url)
            results.append(job)
            if len(results) >= query.limit:
                return sort_jobs(results)
    return sort_jobs(results)


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
