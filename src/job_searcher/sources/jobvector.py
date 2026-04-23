from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote_plus, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class JobvectorSource(JobSource):
    name = "jobvector"
    endpoint = "https://www.jobvector.de"

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

        parser = JobvectorJobsParser(base_url=self.endpoint)
        parser.feed(html)
        for card in parser.cards:
            if not card.url or not card.title:
                continue
            if not matches_query(card.title, card.company, query):
                continue
            if query.location and query.location.lower() not in card.location.lower():
                continue
            yield JobPosting(
                title=card.title,
                company=card.company,
                location=card.location or None,
                source=self.name,
                source_url=canonicalize_job_url(card.url),
                apply_url=canonicalize_job_url(card.url),
                published_at=parse_date(card.published_at),
                tags=("unverified-jobvector",),
            )


@dataclass
class JobvectorJobCard:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    published_at: str = ""


class JobvectorJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://www.jobvector.de") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[JobvectorJobCard] = []
        self._current: JobvectorJobCard | None = None
        self._card_depth = 0
        self._field: str | None = None
        self._field_depth = 0
        self._chunks: list[str] = []
        self._pending_icon: str | None = None
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())

        if tag in {"script", "style", "svg"}:
            self._ignored_depth += 1

        if tag == "article" and "list-item-job" in classes and self._current is None:
            self._current = JobvectorJobCard()
            self._card_depth = 1
            self._pending_icon = None
            return

        if not self._current:
            return

        self._card_depth += 1
        if self._field:
            self._field_depth += 1

        if tag == "a" and "vacancy-title-anchor" in classes:
            href = attrs_dict.get("href") or ""
            if href.startswith("/job/") or href.startswith("https://www.jobvector.de/job/"):
                self._current.url = href if href.startswith("http") else f"{self.base_url}{href}"
        elif tag == "h2":
            self._start_field("title")
        elif tag == "span" and "company-name-text" in classes:
            self._start_field("company")
        elif tag == "div" and "locations-loop-inside-wrapper" in classes:
            self._start_field("location")
        elif tag == "svg":
            icon = attrs_dict.get("data-icon") or ""
            if icon == "calendar-days":
                self._pending_icon = "published_at"
        elif tag == "span" and self._pending_icon == "published_at":
            self._start_field("published_at")

    def handle_data(self, data: str) -> None:
        if self._field and not self._ignored_depth:
            value = data.strip()
            if value:
                self._chunks.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

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
                self._pending_icon = None

        self._card_depth -= 1
        if self._card_depth <= 0:
            if self._current.url and self._current.title:
                self.cards.append(self._current)
            self._current = None
            self._field = None
            self._field_depth = 0
            self._chunks = []
            self._pending_icon = None
            self._ignored_depth = 0

    def _start_field(self, field: str) -> None:
        self._field = field
        self._field_depth = 1
        self._chunks = []


def search_url(query: SearchQuery, endpoint: str = "https://www.jobvector.de") -> str:
    return f"{endpoint}/jobs/{quote_plus(query.title.lower())}/"


def matches_query(title: str, company: str, query: SearchQuery) -> bool:
    haystack = f"{title} {company}".lower()
    title_terms = [term for term in query.title.lower().split() if term]
    return all(term in haystack for term in title_terms)


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
