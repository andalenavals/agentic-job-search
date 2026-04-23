from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class ExperisSource(JobSource):
    name = "experis"
    endpoint = "https://www.experis.de"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            html = fetch_text(
                search_url(query, self.endpoint),
                headers={
                    "Accept": "text/html",
                    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                    "User-Agent": "Mozilla/5.0 (compatible; agentic-job-search/0.1)",
                },
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        parser = ExperisJobsParser(base_url=self.endpoint)
        parser.feed(html)
        for card in parser.cards:
            if not card.url or not card.title:
                continue
            if query.location and query.location.lower() not in card.location.lower():
                continue
            yield JobPosting(
                title=card.title,
                company="Experis",
                location=card.location,
                source=self.name,
                source_url=canonicalize_job_url(card.url),
                apply_url=canonicalize_job_url(card.url),
                published_at=parse_date(card.published_at),
                tags=("unverified-experis",),
            )


@dataclass
class ExperisJobCard:
    title: str = ""
    location: str = ""
    url: str = ""
    published_at: str | None = None


class ExperisJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://www.experis.de") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[ExperisJobCard] = []
        self._current: ExperisJobCard | None = None
        self._card_depth = 0
        self._field: str | None = None
        self._field_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())
        if tag == "div" and {"job-search-result", "card"}.issubset(classes):
            self._current = ExperisJobCard()
            self._card_depth = 1
            return
        if not self._current:
            return

        self._card_depth += 1
        if self._field:
            self._field_depth += 1

        if tag == "a" and "/de/job/" in (attrs_dict.get("href") or ""):
            self._current.url = urljoin(self.base_url, attrs_dict.get("href") or "")
            self._start_field("title")
        elif tag == "div" and "date" in classes:
            self._start_field("published_at")
        elif tag == "div" and "location" in classes:
            self._start_field("location")

    def handle_data(self, data: str) -> None:
        if self._field:
            stripped = data.strip()
            if stripped:
                self._chunks.append(stripped)

    def handle_endtag(self, tag: str) -> None:
        if not self._current:
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

        self._card_depth -= 1
        if self._card_depth <= 0:
            if self._current.url or self._current.title:
                self.cards.append(self._current)
            self._current = None
            self._field = None
            self._field_depth = 0
            self._chunks = []

    def _start_field(self, field: str) -> None:
        self._field = field
        self._field_depth = 1
        self._chunks = []


def search_url(query: SearchQuery, endpoint: str = "https://www.experis.de") -> str:
    return f"{endpoint}/de/search/beruf/{quote(slugify(query.title))}"


def slugify(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
