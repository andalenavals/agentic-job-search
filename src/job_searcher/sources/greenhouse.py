from __future__ import annotations

from collections.abc import Iterable

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def __init__(self, company_token: str) -> None:
        self.company_token = company_token

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.company_token}/jobs?content=true"
        try:
            payload = fetch_json(url)
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}:{self.company_token}: {exc}")
            return ()
        if not isinstance(payload, dict):
            return ()
        jobs = payload.get("jobs", [])
        if not isinstance(jobs, list):
            return ()
        for item in jobs:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            if not title_matches(title, query.title):
                continue
            location = item.get("location") if isinstance(item.get("location"), dict) else {}
            location_name = str(location.get("name") or "")
            if query.location and query.location.lower() not in location_name.lower():
                continue
            company = str(payload.get("name") or self.company_token)
            yield JobPosting(
                title=title,
                company=company,
                location=location_name,
                source=f"{self.name}:{self.company_token}",
                source_url=str(item.get("absolute_url") or ""),
                apply_url=str(item.get("absolute_url") or ""),
                description=str(item.get("content") or ""),
                tags=(self.company_token,),
            )


def title_matches(title: str, query_title: str) -> bool:
    title_lower = title.lower()
    return all(term in title_lower for term in query_title.lower().split() if term)
