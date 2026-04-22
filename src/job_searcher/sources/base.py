from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport


class JobSource(ABC):
    name: str

    @abstractmethod
    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        raise NotImplementedError
