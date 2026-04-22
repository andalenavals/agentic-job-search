from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class IndeedSource(JobSource):
    name = "indeed"
    endpoint = "https://de.indeed.com/jobs"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        params = {
            "q": query.title,
        }
        if query.location:
            params["l"] = query.location
        if query.remote:
            params["sc"] = "0kf:attr(DSQF7);"

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

        parser = IndeedJobsParser(base_url=self.endpoint)
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
                tags=("unverified-indeed",),
            )


@dataclass
class IndeedJobCard:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""


class IndeedJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://www.indeed.com/jobs") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[IndeedJobCard] = []
        self._current: IndeedJobCard | None = None
        self._card_depth = 0
        self._field: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())
        data_testid = attrs_dict.get("data-testid") or ""

        if tag == "div" and "result" in classes and self._current is None:
            self._current = IndeedJobCard()
            self._card_depth = 1
            return

        if not self._current:
            return

        self._card_depth += 1
        if tag == "a" and "jcs-JobTitle" in classes:
            job_key = attrs_dict.get("data-jk") or ""
            if job_key:
                self._current.url = urljoin(self.base_url, f"/viewjob?jk={job_key}")
            else:
                self._current.url = urljoin(self.base_url, attrs_dict.get("href") or "")
        elif tag == "span" and attrs_dict.get("title") and not self._current.title:
            self._current.title = attrs_dict.get("title") or ""
        elif data_testid == "job-title":
            self._start_field("title")
        elif data_testid == "company-name" or "companyName" in classes:
            self._start_field("company")
        elif data_testid in {"text-location", "job-location"} or "companyLocation" in classes:
            self._start_field("location")

    def handle_data(self, data: str) -> None:
        if self._field:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._current:
            return

        if self._field and tag in {"span", "div"}:
            value = " ".join("".join(self._chunks).split())
            if value:
                setattr(self._current, self._field, value)
            self._field = None
            self._chunks = []

        self._card_depth -= 1
        if self._card_depth <= 0:
            if self._current.url or self._current.title:
                self.cards.append(self._current)
            self._current = None
            self._field = None
            self._chunks = []

    def _start_field(self, field: str) -> None:
        self._field = field
        self._chunks = []


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.path == "/viewjob" and parsed.query.startswith("jk="):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query.split("&")[0], ""))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
