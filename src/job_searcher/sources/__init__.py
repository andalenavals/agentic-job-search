from __future__ import annotations

from .arbeitsagentur import ArbeitsagenturSource
from .ashby import AshbySource
from .arbeitnow import ArbeitnowSource
from .berlin_startup_jobs import BerlinStartupJobsSource
from .bund_de import BundDeSource
from .experis import ExperisSource
from .glassdoor import GlassdoorSource
from .google import GoogleSource
from .greenhouse import GreenhouseSource
from .indeed import IndeedSource
from .interamt import InteramtSource
from .karriere_nrw import KarriereNrwSource
from .kununu import KununuSource
from .lever import LeverSource
from .linkedin import LinkedInSource
from .personio import PersonioSource
from .placeholder import PlaceholderSource
from .remote_com import RemoteComSource
from .remotive import RemotiveSource
from .smartrecruiters import SmartRecruitersSource
from .stepstone import StepStoneSource
from .workday import WorkdaySource
from .xing import XingSource

DEFAULT_SOURCES = {
    "agentur": ArbeitsagenturSource,
    "arbeitnow": ArbeitnowSource,
    "berlinstartupjobs": BerlinStartupJobsSource,
    "bund-de": BundDeSource,
    "experis": ExperisSource,
    "glassdoor": GlassdoorSource,
    "google": GoogleSource,
    "indeed": IndeedSource,
    "interamt": InteramtSource,
    "karriere-nrw": KarriereNrwSource,
    "kununu": KununuSource,
    "linkedin": LinkedInSource,
    "remote-com": RemoteComSource,
    "remotive": RemotiveSource,
    "stepstone": StepStoneSource,
    "xing": XingSource,
}

DEFAULT_SOURCE_NAMES = (
    "agentur",
    "arbeitnow",
    "berlinstartupjobs",
    "bund-de",
    "experis",
    "glassdoor",
    "indeed",
    "interamt",
    "karriere-nrw",
    "kununu",
    "linkedin",
    "remote-com",
    "remotive",
    "stepstone",
    "xing",
)

OPTIONAL_COMPANY_SOURCES = {
    "ashby": AshbySource,
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
    "personio": PersonioSource,
    "smartrecruiters": SmartRecruitersSource,
    "workday": WorkdaySource,
}

PLACEHOLDER_SOURCES = {
    "instaffo": "Requires compliant API/browser implementation; direct scraping is not included.",
}


def build_sources(
    names: list[str],
    greenhouse: tuple[str, ...],
    lever: tuple[str, ...],
    ashby: tuple[str, ...] = (),
    personio: tuple[str, ...] = (),
    smartrecruiters: tuple[str, ...] = (),
    workday: tuple[str, ...] = (),
):
    sources = []
    for name in names:
        if name in DEFAULT_SOURCES:
            sources.append(DEFAULT_SOURCES[name]())
        elif name in PLACEHOLDER_SOURCES:
            sources.append(PlaceholderSource(name, PLACEHOLDER_SOURCES[name]))
        else:
            raise ValueError(f"Unknown source: {name}")
    for company in greenhouse:
        sources.append(GreenhouseSource(company))
    for company in lever:
        sources.append(LeverSource(company))
    for company in ashby:
        sources.append(AshbySource(company))
    for company in personio:
        sources.append(PersonioSource(company))
    for company in smartrecruiters:
        sources.append(SmartRecruitersSource(company))
    for site_url in workday:
        sources.append(WorkdaySource(site_url))
    return sources
