from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class LinkedInSource(JobSource):
    name = "linkedin"
    endpoint = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        params = {
            "keywords": query.title,
            "start": "0",
        }
        if query.location:
            params["location"] = query.location
        if query.remote:
            params["f_WT"] = "2"

        try:
            html = fetch_text(
                f"{self.endpoint}?{urlencode(params)}",
                headers={
                    "Accept": "text/html",
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; agentic-job-search/0.1; "
                        "+https://github.com/andalenavals/agentic-job-search)"
                    ),
                },
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()

        parser = LinkedInJobsParser()
        parser.feed(html)
        for card in parser.cards:
            if not card.url or not card.title:
                continue
            yield JobPosting(
                title=card.title,
                company=card.company or "",
                location=card.location,
                source=self.name,
                source_url=canonicalize_job_url(card.url),
                apply_url=canonicalize_job_url(card.url),
                published_at=parse_date(card.published_at),
                tags=("unverified-linkedin",),
            )


@dataclass
class LinkedInJobCard:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    published_at: str | None = None


class LinkedInJobsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[LinkedInJobCard] = []
        self._current: LinkedInJobCard | None = None
        self._card_depth = 0
        self._field: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())
        if tag == "div" and "job-search-card" in classes:
            self._current = LinkedInJobCard()
            self._card_depth = 1
            return

        if not self._current:
            return

        self._card_depth += 1
        if tag == "a" and "base-card__full-link" in classes:
            self._current.url = attrs_dict.get("href") or ""
        elif tag == "h3" and "base-search-card__title" in classes:
            self._start_field("title")
        elif tag == "h4" and "base-search-card__subtitle" in classes:
            self._start_field("company")
        elif tag == "span" and "job-search-card__location" in classes:
            self._start_field("location")
        elif tag == "time" and "job-search-card__listdate" in classes:
            self._current.published_at = attrs_dict.get("datetime")

    def handle_data(self, data: str) -> None:
        if self._field:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._current:
            return

        if self._field and tag in {"h3", "h4", "span"}:
            value = " ".join("".join(self._chunks).split())
            setattr(self._current, self._field, value)
            self._field = None
            self._chunks = []

        self._card_depth -= 1
        if self._card_depth <= 0:
            self.cards.append(self._current)
            self._current = None
            self._field = None
            self._chunks = []

    def _start_field(self, field: str) -> None:
        self._field = field
        self._chunks = []


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
