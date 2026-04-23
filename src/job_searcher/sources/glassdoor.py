from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class GlassdoorSource(JobSource):
    name = "glassdoor"
    endpoint = "https://www.glassdoor.de/Job/jobs.htm"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        params = {"sc.keyword": query.title}
        if query.location:
            params["locKeyword"] = query.location
        if query.remote:
            params["remoteWorkType"] = "1"

        try:
            html = fetch_text(
                f"{self.endpoint}?{urlencode(params)}",
                headers={
                    "Accept": "text/html",
                    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
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

        parser = GlassdoorJobsParser(base_url=self.endpoint)
        parser.feed(html)
        for card in parser.cards:
            if not card.url or not card.title:
                continue
            yield JobPosting(
                title=card.title,
                company=card.company,
                location=card.location,
                source=self.name,
                source_url=canonicalize_job_url(card.url),
                apply_url=canonicalize_job_url(card.url),
                tags=("unverified-glassdoor",),
            )


@dataclass
class GlassdoorJobCard:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""


class GlassdoorJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://www.glassdoor.de") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[GlassdoorJobCard] = []
        self._current: GlassdoorJobCard | None = None
        self._card_depth = 0
        self._field: str | None = None
        self._field_depth = 0
        self._ignored_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg"}:
            self._ignored_depth += 1

        attrs_dict = dict(attrs)
        data_test = attrs_dict.get("data-test") or attrs_dict.get("data-testid") or ""

        if data_test == "jobListing" and self._current is None:
            self._current = GlassdoorJobCard()
            self._card_depth = 1
            return

        if not self._current:
            return

        self._card_depth += 1
        if self._field:
            self._field_depth += 1

        if tag == "a" and data_test in {"job-link", "job-title"}:
            self._current.url = urljoin(self.base_url, attrs_dict.get("href") or "")
            self._start_field("title")
        elif data_test == "job-title":
            self._start_field("title")
        elif data_test in {"employer-name", "employerName"}:
            self._start_field("company")
        elif data_test in {"emp-location", "job-location", "location"}:
            self._start_field("location")

    def handle_data(self, data: str) -> None:
        if self._field and not self._ignored_depth:
            stripped = data.strip()
            if stripped:
                self._chunks.append(stripped)

    def handle_endtag(self, tag: str) -> None:
        if not self._current:
            if tag in {"script", "style", "svg"} and self._ignored_depth:
                self._ignored_depth -= 1
            return

        if tag in {"script", "style", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

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
            self._ignored_depth = 0
            self._chunks = []

    def _start_field(self, field: str) -> None:
        self._field = field
        self._field_depth = 1
        self._ignored_depth = 0
        self._chunks = []


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
