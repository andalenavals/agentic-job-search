from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class StepStoneSource(JobSource):
    name = "stepstone"
    endpoint = "https://www.stepstone.de"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            html = fetch_text(
                search_url(query, self.endpoint),
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

        parser = StepStoneJobsParser(base_url=self.endpoint)
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
                tags=("unverified-stepstone",),
            )


@dataclass
class StepStoneJobCard:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""


class StepStoneJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://www.stepstone.de") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[StepStoneJobCard] = []
        self._current: StepStoneJobCard | None = None
        self._card_depth = 0
        self._field: str | None = None
        self._field_depth = 0
        self._ignored_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg"}:
            self._ignored_depth += 1

        attrs_dict = dict(attrs)
        data_at = attrs_dict.get("data-at") or ""
        data_testid = attrs_dict.get("data-testid") or ""

        if tag == "article" and data_at == "job-item" and self._current is None:
            self._current = StepStoneJobCard()
            self._card_depth = 1
            return

        if not self._current:
            return

        self._card_depth += 1
        if self._field:
            self._field_depth += 1

        if tag == "a" and data_at == "job-item-title":
            self._current.url = urljoin(self.base_url, attrs_dict.get("href") or "")
            self._start_field("title")
        elif data_at == "job-item-company-name":
            self._start_field("company")
        elif data_at == "job-item-location":
            self._start_field("location")
        elif data_testid == "job-item-title" and tag == "a":
            self._current.url = urljoin(self.base_url, attrs_dict.get("href") or "")
            self._start_field("title")

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


def search_url(query: SearchQuery, endpoint: str = "https://www.stepstone.de") -> str:
    title_slug = slugify(query.title)
    if query.location:
        return f"{endpoint}/jobs/{quote(title_slug)}/in-{quote(slugify(query.location))}"
    return f"{endpoint}/jobs/{quote(title_slug)}"


def slugify(value: str) -> str:
    parts = []
    current = []
    for char in value.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    return "-".join(parts)


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
