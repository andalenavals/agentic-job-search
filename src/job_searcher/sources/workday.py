from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class WorkdaySource(JobSource):
    name = "workday"

    def __init__(self, site_url: str) -> None:
        self.site_url = site_url

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            html = fetch_text(
                self.site_url,
                headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"},
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}:{self.site_url}: {exc}")
            return ()
        parser = WorkdayJobsParser(self.site_url)
        parser.feed(html)
        for card in parser.cards:
            if not title_matches(card.title, query.title):
                continue
            yield JobPosting(
                title=card.title,
                company=company_from_url(self.site_url),
                location=query.location or "",
                source=f"{self.name}:{company_from_url(self.site_url)}",
                source_url=canonicalize_job_url(card.url),
                apply_url=canonicalize_job_url(card.url),
                tags=("workday",),
            )


@dataclass
class WorkdayJobCard:
    title: str = ""
    url: str = ""


class WorkdayJobsParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[WorkdayJobCard] = []
        self._current_url = ""
        self._capture = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href") or ""
        if tag == "a" and "/job/" in href:
            self._current_url = urljoin(self.base_url, href)
            self._capture = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            value = data.strip()
            if value:
                self._chunks.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture:
            title = " ".join(" ".join(self._chunks).split())
            if title and self._current_url and all(card.url != self._current_url for card in self.cards):
                self.cards.append(WorkdayJobCard(title=title, url=self._current_url))
            self._current_url = ""
            self._capture = False
            self._chunks = []


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def company_from_url(url: str) -> str:
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    return host.split(".")[0] if host else "workday"


def title_matches(title: str, query_title: str) -> bool:
    title_lower = title.lower()
    return all(term in title_lower for term in query_title.lower().split() if term)
