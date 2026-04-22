from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class ArbeitnowSource(JobSource):
    name = "arbeitnow"
    endpoint = "https://www.arbeitnow.com/api/job-board-api"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            payload = fetch_json(self.endpoint)
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()
        if not isinstance(payload, dict):
            return ()
        jobs = payload.get("data", [])
        if not isinstance(jobs, list):
            return ()
        for item in jobs:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            company = str(item.get("company_name") or "")
            if not matches_query(title, company, query):
                continue
            location = str(item.get("location") or "")
            if query.location and query.location.lower() not in location.lower():
                continue
            created_at = parse_unix_timestamp(item.get("created_at"))
            yield JobPosting(
                title=title,
                company=company,
                location=location,
                source=self.name,
                source_url=str(item.get("url") or ""),
                apply_url=str(item.get("url") or ""),
                description=strip_html(str(item.get("description") or "")),
                published_at=created_at,
                tags=tuple(str(tag) for tag in item.get("tags", []) if tag),
            )


def matches_query(title: str, company: str, query: SearchQuery) -> bool:
    haystack = f"{title} {company}".lower()
    title_terms = [term for term in query.title.lower().split() if term]
    if title_terms and not all(term in haystack for term in title_terms):
        return False
    return True


def parse_unix_timestamp(value: object) -> datetime | None:
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def strip_html(value: str) -> str:
    result = []
    in_tag = False
    for char in value:
        if char == "<":
            in_tag = True
            continue
        if char == ">":
            in_tag = False
            result.append(" ")
            continue
        if not in_tag:
            result.append(char)
    return " ".join("".join(result).split())
