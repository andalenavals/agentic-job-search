from __future__ import annotations

from collections.abc import Iterable

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class SmartRecruitersSource(JobSource):
    name = "smartrecruiters"

    def __init__(self, company_token: str) -> None:
        self.company_token = company_token

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        url = f"https://api.smartrecruiters.com/v1/companies/{self.company_token}/postings?limit=100"
        try:
            payload = fetch_json(url)
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}:{self.company_token}: {exc}")
            return ()
        for item in extract_postings(payload):
            title = str(item.get("name") or item.get("title") or "")
            if not title_matches(title, query.title):
                continue
            location = location_name(item)
            if query.location and query.location.lower() not in location.lower():
                continue
            posting_url = str(item.get("ref") or item.get("url") or "")
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


def extract_postings(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    content = payload.get("content")
    if isinstance(content, list):
        return [item for item in content if isinstance(item, dict)]
    postings = payload.get("postings")
    if isinstance(postings, list):
        return [item for item in postings if isinstance(item, dict)]
    return []


def location_name(item: dict[str, object]) -> str:
    location = item.get("location")
    if not isinstance(location, dict):
        return ""
    parts = [
        location.get("city"),
        location.get("region"),
        location.get("country"),
    ]
    return ", ".join(str(part) for part in parts if part)


def title_matches(title: str, query_title: str) -> bool:
    title_lower = title.lower()
    return all(term in title_lower for term in query_title.lower().split() if term)
