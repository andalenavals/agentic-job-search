from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class XingSource(JobSource):
    name = "xing"
    endpoint = "https://www.xing.com"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        url = search_url(query, self.endpoint)
        try:
            html = fetch_text(url, headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"})
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()
        parser = XingJobsParser(self.endpoint)
        parser.feed(html)
        for card in parser.cards:
            if not card.url or not card.title:
                continue
            yield JobPosting(
                title=card.title,
                company=card.company,
                location=query.location or "",
                source=self.name,
                source_url=canonicalize_job_url(card.url),
                apply_url=canonicalize_job_url(card.url),
                tags=("unverified-xing",),
            )


@dataclass
class XingJobCard:
    title: str = ""
    company: str = ""
    url: str = ""


class XingJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://www.xing.com") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[XingJobCard] = []
        self._current_url: str = ""
        self._capture_title = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href") or ""
        if tag == "a" and "/jobs/" in href and not href.rstrip("/").endswith("/jobs"):
            self._current_url = urljoin(self.base_url, href)
            self._capture_title = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            value = data.strip()
            if value:
                self._chunks.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            title = " ".join(" ".join(self._chunks).split())
            if title and self._current_url:
                if all(card.url != self._current_url for card in self.cards):
                    self.cards.append(XingJobCard(title=title, url=self._current_url))
            self._current_url = ""
            self._capture_title = False
            self._chunks = []


def search_url(query: SearchQuery, endpoint: str = "https://www.xing.com") -> str:
    title = slugify(query.title)
    if query.location:
        return f"{endpoint}/jobs/{slugify(query.location)}-{title}"
    return f"{endpoint}/jobs/{quote(title)}"


def slugify(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
