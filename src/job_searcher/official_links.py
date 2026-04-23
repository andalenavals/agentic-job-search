from __future__ import annotations

from urllib.parse import urlparse

AGGREGATOR_HOST_PARTS = (
    "berlinstartupjobs",
    "linkedin.",
    "glassdoor.",
    "stepstone.",
    "instaffo.",
    "indeed.",
    "kununu.",
    "monster.",
    "xing.",
)

OFFICIAL_HOST_PARTS = (
    "bund.de",
    "greenhouse.io",
    "interamt.de",
    "karriere.nrw",
    "lever.co",
    "ashbyhq.com",
    "workdayjobs.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "personio.de",
    "personio.com",
    "bamboohr.com",
    "arbeitsagentur.de",
    "jobs.ashbyhq.com",
    "careers.",
    "jobs.",
)


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def is_likely_official_application(url: str, company: str | None = None) -> bool:
    parsed_host = host(url)
    if not parsed_host:
        return False
    if any(part in parsed_host for part in AGGREGATOR_HOST_PARTS):
        return False
    if any(part in parsed_host for part in OFFICIAL_HOST_PARTS):
        return True
    if company:
        normalized_company = "".join(ch for ch in company.lower() if ch.isalnum())
        normalized_host = "".join(ch for ch in parsed_host if ch.isalnum())
        if normalized_company and normalized_company in normalized_host:
            return True
    return False
