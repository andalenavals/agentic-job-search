from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource
from job_searcher.sources.xing import XingJobsParser


class InteramtSource(JobSource):
    name = "interamt"
    endpoint = "https://interamt.de"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        params = {"search": query.title}
        if query.location:
            params["location"] = query.location
        try:
            html = fetch_text(
                f"{self.endpoint}/stellensuche?{urlencode(params)}",
                headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"},
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()
        parser = XingJobsParser(self.endpoint)
        parser.feed(html.replace("/stellenangebot/", "/jobs/stellenangebot/"))
        for card in parser.cards:
            url = canonicalize_job_url(card.url.replace("/jobs/stellenangebot/", "/stellenangebot/"))
            yield JobPosting(
                title=card.title,
                company="",
                location=query.location or "",
                source=self.name,
                source_url=url,
                apply_url=url,
                tags=("unverified-interamt",),
            )


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
