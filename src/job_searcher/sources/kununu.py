from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from html import unescape
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class KununuSource(JobSource):
    name = "kununu"
    endpoint = "https://www.kununu.com"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            html = fetch_text(
                search_url(query, self.endpoint),
                headers={
                    "Accept": "text/html",
                    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    ),
                },
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        try:
            jobs = extract_jobs(html)
        except ValueError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        for item in jobs:
            if not isinstance(item, dict):
                continue
            profile = item.get("profile") if isinstance(item.get("profile"), dict) else {}
            url = str(item.get("url") or "")
            title = str(item.get("title") or "")
            if not url or not title:
                continue
            yield JobPosting(
                title=title,
                company=str(profile.get("companyName") or ""),
                location=format_location(item),
                source=self.name,
                source_url=canonicalize_job_url(urljoin(self.endpoint, url)),
                apply_url=canonicalize_job_url(urljoin(self.endpoint, url)),
                published_at=parse_date(item.get("postedAt")),
                tags=("unverified-kununu",),
            )


def extract_jobs(html: str) -> list[dict[object, object]]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("Could not find Kununu __NEXT_DATA__ payload")
    try:
        payload = json.loads(unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse Kununu __NEXT_DATA__ payload: {exc}") from exc
    page_props = payload.get("props", {}).get("pageProps", {})
    search_jobs = page_props.get("searchJobs", {})
    jobs = search_jobs.get("jobs", [])
    if not isinstance(jobs, list):
        raise ValueError("Kununu searchJobs payload did not contain a jobs list")
    return jobs


def search_url(query: SearchQuery, endpoint: str = "https://www.kununu.com") -> str:
    path = f"/de/jobs/j-{slugify(query.title)}"
    if query.location:
        location_slug = slugify(query.location)
        if location_slug == "berlin":
            path = f"{path}/l-state-berlin"
        else:
            path = f"{path}/l-{location_slug}"
    return f"{endpoint}{quote(path, safe='/')}"


def slugify(value: str) -> str:
    parts = []
    current = []
    for char in value.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    return "-".join(parts)


def format_location(item: dict[object, object]) -> str:
    parts = [
        str(item.get("city") or ""),
        str(item.get("region") or ""),
    ]
    return ", ".join(dict.fromkeys(part for part in parts if part))


def parse_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
