from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from urllib.parse import quote, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class RemoteComSource(JobSource):
    name = "remote-com"
    endpoint = "https://remote.com"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            html = fetch_text(
                search_url(query, self.endpoint),
                headers={
                    "Accept": "text/html",
                    "Accept-Language": "en-US,en;q=0.9",
                    "User-Agent": "Mozilla/5.0 (compatible; agentic-job-search/0.1)",
                },
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        try:
            jobs = extract_jobs(html)
        except ValueError as exc:
            if "Could not find Remote.com jobsData payload" in str(exc):
                return ()
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        for item in jobs:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            apply_url = str(item.get("applyUrl") or "")
            slug = str(item.get("slug") or "")
            if not title or not apply_url:
                continue
            location = format_location(item)
            if query.location and not query.remote and query.location.lower() not in location.lower():
                continue
            company = item.get("companyProfile") if isinstance(item.get("companyProfile"), dict) else {}
            yield JobPosting(
                title=title,
                company=str(company.get("name") or ""),
                location=location,
                source=self.name,
                source_url=canonicalize_job_url(f"{self.endpoint}/jobs/{slug}") if slug else apply_url,
                apply_url=canonicalize_job_url(apply_url),
                published_at=parse_iso_datetime(item.get("publishedAt")),
                tags=("remote",),
            )


def extract_jobs(html: str) -> list[dict[object, object]]:
    marker = '\\"jobsData\\":'
    index = html.find(marker)
    if index == -1:
        raise ValueError("Could not find Remote.com jobsData payload")
    escaped = html[index + len(marker) :]
    decoded = escaped.encode("utf-8").decode("unicode_escape")
    try:
        payload, _ = json.JSONDecoder().raw_decode(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse Remote.com jobsData payload: {exc}") from exc
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        raise ValueError("Remote.com jobsData payload did not contain a jobs list")
    return jobs


def search_url(query: SearchQuery, endpoint: str = "https://remote.com") -> str:
    return f"{endpoint}/jobs/types-of-remote-jobs/remote-{quote(slugify(query.title))}-jobs"


def slugify(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def format_location(item: dict[object, object]) -> str:
    hiring_location = item.get("hiringLocation") if isinstance(item.get("hiringLocation"), dict) else {}
    locations = hiring_location.get("includedLocations", [])
    if isinstance(locations, list):
        names = []
        for location in locations:
            if not isinstance(location, dict):
                continue
            value = location.get("value") if isinstance(location.get("value"), dict) else {}
            name = str(value.get("name") or "")
            if name:
                names.append(name)
        if names:
            return ", ".join(dict.fromkeys(names))
    return "Remote"


def parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
