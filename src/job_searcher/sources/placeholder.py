from __future__ import annotations

from collections.abc import Iterable

from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class PlaceholderSource(JobSource):
    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        if report:
            report.warn(f"Skipped {self.name}: {self.reason}")
        return ()
