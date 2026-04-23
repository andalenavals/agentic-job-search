from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class BundDeSource(JobSource):
    name = "bund-de"
    endpoint = "https://www.service.bund.de"

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        try:
            html = fetch_text(
                search_url(query, self.endpoint),
                headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"},
            )
        except FetchError as exc:
            if report:
                report.warn(f"Skipped {self.name}: {exc}")
            return ()
        parser = BundDeJobsParser(self.endpoint)
        parser.feed(html)
        for card in parser.cards:
            if query.location and query.location.lower() not in card.location.lower():
                continue
            yield JobPosting(
                title=card.title,
                company=card.company,
                location=card.location,
                source=self.name,
                source_url=canonicalize_job_url(card.url),
                apply_url=canonicalize_job_url(card.url),
                tags=("official-bund-de",),
            )


@dataclass
class BundDeJobCard:
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""


class BundDeJobsParser(HTMLParser):
    def __init__(self, base_url: str = "https://www.service.bund.de") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[BundDeJobCard] = []
        self._current_href = ""
        self._chunks: list[str] = []
        self._capture = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href") or ""
        if tag == "a" and ("Stellenangebote" in href or "stellenangebot" in href.lower()):
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
            if title and self._current_href:
                if all(card.url != self._current_href for card in self.cards):
                    self.cards.append(
                        BundDeJobCard(
                            title=clean_result_title(title),
                            company=company_from_result_text(title),
                            url=self._current_href,
                        )
                    )
            self._capture = False
            self._current_href = ""
            self._chunks = []


def canonicalize_job_url(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.split(";jsessionid=", 1)[0]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def search_url(query: SearchQuery, endpoint: str = "https://www.service.bund.de") -> str:
    params = {
        "nn": "4642046",
        "type": "0",
        "searchResult": "true",
        "templateQueryString": query.title,
    }
    if query.location:
        params["city_zipcode"] = query.location
    return f"{endpoint}/Content/DE/Stellen/Suche/Formular.html?{urlencode(params)}"


def clean_result_title(value: str) -> str:
    value = remove_soft_hyphens(value)
    value = re.sub(r"^Stellenbezeichnung\s+", "", value)
    value = value.split(" Arbeitgeber ", 1)[0]
    return " ".join(value.split())


def company_from_result_text(value: str) -> str:
    value = remove_soft_hyphens(value)
    match = re.search(r" Arbeitgeber (.*?) Veröffentlicht ", value)
    return " ".join(match.group(1).split()) if match else ""


def remove_soft_hyphens(value: str) -> str:
    return value.replace("\xad", "")
