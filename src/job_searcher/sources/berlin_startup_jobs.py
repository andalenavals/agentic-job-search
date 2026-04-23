from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class BerlinStartupJobsSource(JobSource):
    name = "berlinstartupjobs"
    endpoint = "https://berlinstartupjobs.com"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            html = fetch_text(
                f"{self.endpoint}/?{urlencode({'s': query.title})}",
                headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"},
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        parser = BerlinStartupJobsParser(self.endpoint)
        parser.feed(html)
        for card in parser.cards:
            if not card.url or not card.title:
                continue
            location = card.location or "Berlin"
            if query.location and query.location.lower() not in location.lower():
                continue
            yield JobPosting(
                title=card.title,
                company=card.company,
                location=location,
                source=self.name,
                source_url=canonicalize_job_url(card.url),
                apply_url=canonicalize_job_url(card.url),
                tags=("unverified-berlinstartupjobs",),
            )


@dataclass
class BerlinStartupJobCard:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""


class BerlinStartupJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://berlinstartupjobs.com") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[BerlinStartupJobCard] = []
        self._in_article = False
        self._article_depth = 0
        self._field: str | None = None
        self._field_depth = 0
        self._chunks: list[str] = []
        self._current = BerlinStartupJobCard()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())
        if tag == "article" and not self._in_article:
            self._in_article = True
            self._article_depth = 1
            self._current = BerlinStartupJobCard()
            return
        if not self._in_article:
            return
        self._article_depth += 1
        if self._field:
            self._field_depth += 1
        if tag == "a" and not self._current.url:
            href = attrs_dict.get("href") or ""
            if href and "/jobs/" in href:
                self._current.url = urljoin(self.base_url, href)
                self._start_field("title")
        elif "company" in classes:
            self._start_field("company")
        elif "location" in classes:
            self._start_field("location")

    def handle_data(self, data: str) -> None:
        if self._field:
            value = data.strip()
            if value:
                self._chunks.append(value)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_article:
            return
        if self._field:
            self._field_depth -= 1
            if self._field_depth <= 0:
                value = " ".join(" ".join(self._chunks).split())
                if value:
                    setattr(self._current, self._field, value)
                self._field = None
                self._field_depth = 0
                self._chunks = []
        self._article_depth -= 1
        if self._article_depth <= 0:
            if self._current.url and self._current.title:
                self.cards.append(self._current)
            self._in_article = False

    def _start_field(self, field: str) -> None:
        self._field = field
        self._field_depth = 1
        self._chunks = []


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
