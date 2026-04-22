from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from urllib.parse import quote_plus

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class RemotiveSource(JobSource):
    name = "remotive"
    endpoint = "https://remotive.com/api/remote-jobs"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        url = f"{self.endpoint}?search={quote_plus(query.title)}"
        try:
            payload = fetch_json(url)
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
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
            company = str(item.get("company_name") or "")
            if not matches_query(title, company, query):
                continue
            if query.location and "remote" not in query.location.lower():
                continue
            yield JobPosting(
                title=title,
                company=company,
                location=str(item.get("candidate_required_location") or "Remote"),
                source=self.name,
                source_url=str(item.get("url") or ""),
                apply_url=str(item.get("url") or ""),
                description=str(item.get("description") or ""),
                published_at=parse_iso_datetime(item.get("publication_date")),
                tags=tuple(str(tag) for tag in item.get("tags", []) if tag),
            )


def parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def matches_query(title: str, company: str, query: SearchQuery) -> bool:
    haystack = f"{title} {company}".lower()
    title_terms = [term for term in query.title.lower().split() if term]
    return all(term in haystack for term in title_terms)
