from __future__ import annotations

from collections.abc import Iterable

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class AshbySource(JobSource):
    name = "ashby"

    def __init__(self, company_token: str) -> None:
        self.company_token = company_token

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.company_token}"
        try:
            payload = fetch_json(url)
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}:{self.company_token}: {exc}")
            return ()
        for item in extract_jobs(payload):
            title = str(item.get("title") or "")
            if not title_matches(title, query.title):
                continue
            location = ashby_location(item)
            if query.location and query.location.lower() not in location.lower():
                continue
            posting_url = ashby_url(item)
            if not posting_url:
                continue
            yield JobPosting(
                title=title,
                company=self.company_token,
                location=location,
                source=f"{self.name}:{self.company_token}",
                source_url=posting_url,
                apply_url=posting_url,
                tags=(self.company_token,),
            )


def extract_jobs(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return []
    return [item for item in jobs if isinstance(item, dict)]


def ashby_location(item: dict[str, object]) -> str:
    location = item.get("location")
    if isinstance(location, str):
        return location
    if isinstance(location, dict):
        return str(location.get("name") or location.get("displayName") or "")
    return ""


def ashby_url(item: dict[str, object]) -> str:
    return str(item.get("jobUrl") or item.get("applyUrl") or item.get("url") or "")


def title_matches(title: str, query_title: str) -> bool:
    title_lower = title.lower()
    return all(term in title_lower for term in query_title.lower().split() if term)
