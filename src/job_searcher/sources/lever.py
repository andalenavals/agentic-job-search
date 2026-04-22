from __future__ import annotations

from collections.abc import Iterable

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class LeverSource(JobSource):
    name = "lever"

    def __init__(self, company_token: str) -> None:
        self.company_token = company_token

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        url = f"https://api.lever.co/v0/postings/{self.company_token}?mode=json"
        try:
            payload = fetch_json(url)
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}:{self.company_token}: {exc}")
            return ()
        if not isinstance(payload, list):
            return ()
        for item in payload:
            if not isinstance(item, dict):
                continue
            title = str(item.get("text") or "")
            if not title_matches(title, query.title):
                continue
            categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
            location = str(categories.get("location") or "")
            if query.location and query.location.lower() not in location.lower():
                continue
            yield JobPosting(
                title=title,
                company=self.company_token,
                location=location,
                source=f"{self.name}:{self.company_token}",
                source_url=str(item.get("hostedUrl") or ""),
                apply_url=str(item.get("applyUrl") or item.get("hostedUrl") or ""),
                description=str(item.get("descriptionPlain") or ""),
                tags=tuple(str(value) for value in categories.values() if value),
            )


def title_matches(title: str, query_title: str) -> bool:
    title_lower = title.lower()
    return all(term in title_lower for term in query_title.lower().split() if term)
