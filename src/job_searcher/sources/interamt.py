from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text_with_cookies
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class InteramtSource(JobSource):
    name = "interamt"
    endpoint = "https://interamt.de"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        params = {"search": query.title}
        if query.location:
            params["location"] = query.location
        try:
            html = fetch_text_with_cookies(
                f"{self.endpoint}/koop/app/stellensuche?{urlencode(params)}",
                headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"},
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()
        parser = InteramtJobsParser(self.endpoint)
        parser.feed(html)
        for card in parser.cards:
            url = canonicalize_job_url(card.url)
            yield JobPosting(
                title=card.title,
                company=card.company,
                location=query.location or "",
                source=self.name,
                source_url=url,
                apply_url=url,
                tags=("official-interamt",),
            )


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


@dataclass
class InteramtJobCard:
    title: str = ""
    company: str = ""
    url: str = ""


class InteramtJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://interamt.de") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[InteramtJobCard] = []
        self._current_href = ""
        self._capture = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href") or ""
        href_lower = href.lower()
        if tag == "a" and is_job_href(href_lower):
            self._current_href = urljoin(self.base_url, href)
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
            if title and self._current_href and all(card.url != self._current_href for card in self.cards):
                self.cards.append(InteramtJobCard(title=title, url=self._current_href))
            self._current_href = ""
            self._capture = False
            self._chunks = []


def is_job_href(href: str) -> bool:
    parsed = urlsplit(href)
    path = parsed.path.lower()
    return "stellenangebot/" in path or "stellenangebote/" in path
