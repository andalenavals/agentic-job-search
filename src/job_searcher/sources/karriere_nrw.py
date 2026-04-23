from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class KarriereNrwSource(JobSource):
    name = "karriere-nrw"
    endpoint = "https://api.karriere.nrw/v1.0/opennrw/suche"
    public_endpoint = "https://www.karriere.nrw"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            payload = fetch_json(
                self.endpoint,
                headers={"Email": "agentic-job-search@example.invalid"},
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        if not isinstance(payload, dict):
            return ()
        results = payload.get("results", [])
        if not isinstance(results, list):
            return ()

        for item in results:
            if not isinstance(item, dict):
                continue
            if not matches_query(item, query):
                continue
            uuid = str(item.get("uuid") or "")
            if not uuid:
                continue
            url = public_job_url(uuid, self.public_endpoint)
            yield JobPosting(
                title=str(item.get("titel_der_stelle") or ""),
                company=str(item.get("ausschreibende_behoerde") or ""),
                location=format_location(item),
                source=self.name,
                source_url=url,
                apply_url=url,
                published_at=parse_date(item.get("erscheinungsdatum")),
                tags=("official-karriere-nrw",),
            )


def matches_query(item: dict[object, object], query: SearchQuery) -> bool:
    haystack = " ".join(
        [
            str(item.get("titel_der_stelle") or ""),
            str(item.get("ausschreibende_behoerde") or ""),
            str(item.get("ort") or ""),
        ]
    ).lower()
    title_terms = [term for term in query.title.lower().split() if term]
    if title_terms and not all(term in haystack for term in title_terms):
        return False
    if query.location and query.location.lower() not in str(item.get("ort") or "").lower():
        return False
    return True


def public_job_url(uuid: str, endpoint: str = "https://www.karriere.nrw") -> str:
    return canonicalize_job_url(f"{endpoint}/stellenausschreibung/{uuid}")


def format_location(item: dict[object, object]) -> str:
    parts = [str(item.get("ort") or ""), str(item.get("plz") or "")]
    return ", ".join(part for part in parts if part)


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
