from __future__ import annotations

import os
from collections.abc import Iterable
from urllib.parse import urlencode, urlparse, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class GoogleSource(JobSource):
    name = "google"
    endpoint = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str | None = None, search_engine_id: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("GOOGLE_SEARCH_API_KEY")
        self.search_engine_id = search_engine_id or os.environ.get("GOOGLE_SEARCH_ENGINE_ID")

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        if not self.api_key or not self.search_engine_id:
            if report:
                report.warn(
                    "Skipped google: set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID "
                    "to use Google Programmable Search."
                )
            return ()

        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": build_google_query(query),
            "num": str(min(max(query.limit, 1), 10)),
        }
        try:
            payload = fetch_json(f"{self.endpoint}?{urlencode(params)}")
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        if not isinstance(payload, dict):
            return ()
        items = payload.get("items", [])
        if not isinstance(items, list):
            return ()
        for item in items:
            if not isinstance(item, dict):
                continue
            link = str(item.get("link") or "")
            title = clean_title(str(item.get("title") or ""))
            if not link or not title:
                continue
            yield JobPosting(
                title=title,
                company=company_from_url(link),
                location=query.location or ("Remote" if query.remote else ""),
                source=self.name,
                source_url=canonicalize_job_url(link),
                apply_url=canonicalize_job_url(link),
                description=str(item.get("snippet") or ""),
                tags=("google-search",),
            )


def build_google_query(query: SearchQuery) -> str:
    parts = [
        query.title,
        "job",
        "apply",
        "careers",
        "-site:linkedin.com",
        "-site:indeed.com",
        "-site:glassdoor.com",
        "-site:glassdoor.de",
        "-site:stepstone.de",
        "-site:kununu.com",
    ]
    if query.location:
        parts.append(query.location)
    if query.remote:
        parts.append("remote")
    return " ".join(part for part in parts if part)


def clean_title(title: str) -> str:
    separators = [" | ", " - ", " – "]
    cleaned = title
    for separator in separators:
        if separator in cleaned:
            cleaned = cleaned.split(separator)[0]
            break
    return " ".join(cleaned.split())


def company_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2]
    return host


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
