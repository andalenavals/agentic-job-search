from __future__ import annotations

from collections.abc import Iterable
from xml.etree import ElementTree

from job_searcher.http import FetchError, fetch_text
from job_searcher.models import JobPosting, SearchQuery
from job_searcher.reporting import SearchReport
from job_searcher.sources.base import JobSource


class PersonioSource(JobSource):
    name = "personio"

    def __init__(self, company_token: str) -> None:
        self.company_token = company_token

    def search(self, query: SearchQuery, report: SearchReport | None = None) -> Iterable[JobPosting]:
        for url in feed_urls(self.company_token):
            try:
                xml = fetch_text(url)
                positions = parse_positions(xml)
                break
            except (FetchError, ElementTree.ParseError) as exc:
                last_error = exc
        else:
            if report:
                report.warn(f"Skipped {self.name}:{self.company_token}: {last_error}")
            return ()

        for position in positions:
            title = text_value(position, "name")
            if not title_matches(title, query.title):
                continue
            location = text_value(position, "office")
            if query.location and query.location.lower() not in location.lower():
                continue
            posting_url = personio_url(self.company_token, text_value(position, "id"))
            yield JobPosting(
                title=title,
                company=self.company_token,
                location=location,
                source=f"{self.name}:{self.company_token}",
                source_url=posting_url,
                apply_url=posting_url,
                tags=tuple(
                    value
                    for value in (
                        text_value(position, "recruitingCategory"),
                        text_value(position, "employmentType"),
                    )
                    if value
                ),
            )


def feed_urls(company_token: str) -> tuple[str, str]:
    return (
        f"https://{company_token}.jobs.personio.de/xml",
        f"https://{company_token}.jobs.personio.com/xml",
    )


def parse_positions(xml: str) -> list[ElementTree.Element]:
    root = ElementTree.fromstring(xml)
    return list(root.findall(".//position"))


def text_value(position: ElementTree.Element, tag: str) -> str:
    node = position.find(tag)
    return "".join(node.itertext()).strip() if node is not None else ""


def personio_url(company_token: str, job_id: str) -> str:
    return f"https://{company_token}.jobs.personio.de/job/{job_id}"


def title_matches(title: str, query_title: str) -> bool:
    title_lower = title.lower()
    return all(term in title_lower for term in query_title.lower().split() if term)
