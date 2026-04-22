from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from urllib.parse import urlencode

from job_searcher.http import FetchError, fetch_json
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class ArbeitsagenturSource(JobSource):
    name = "agentur"
    endpoint = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
    api_key = "jobboerse-jobsuche"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        params = {
            "angebotsart": "1",
            "was": query.title,
            "page": "1",
            "size": str(max(query.limit, 25)),
            "pav": "false",
        }
        if query.location:
            params["wo"] = query.location
        if query.remote:
            params["arbeitszeit"] = "ho"

        try:
            payload = fetch_json(
                f"{self.endpoint}?{urlencode(params)}",
                headers={"X-API-Key": self.api_key},
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        if not isinstance(payload, dict):
            return ()
        jobs = payload.get("stellenangebote", [])
        if not isinstance(jobs, list):
            return ()

        for item in jobs:
            if not isinstance(item, dict):
                continue
            refnr = str(item.get("refnr") or "")
            if not refnr:
                continue
            location = item.get("arbeitsort") if isinstance(item.get("arbeitsort"), dict) else {}
            yield JobPosting(
                title=str(item.get("titel") or item.get("beruf") or ""),
                company=str(item.get("arbeitgeber") or ""),
                location=format_location(location),
                source=self.name,
                source_url=job_detail_url(refnr),
                apply_url=job_detail_url(refnr),
                published_at=parse_date(item.get("aktuelleVeroeffentlichungsdatum")),
                tags=tuple(tag for tag in [str(item.get("beruf") or "")] if tag),
            )


def job_detail_url(refnr: str) -> str:
    return f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"


def format_location(location: dict[object, object]) -> str:
    parts = [
        str(location.get("ort") or ""),
        str(location.get("region") or ""),
        str(location.get("land") or ""),
    ]
    return ", ".join(dict.fromkeys(part for part in parts if part))


def parse_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
