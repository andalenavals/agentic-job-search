from __future__ import annotations

from .arbeitsagentur import ArbeitsagenturSource
from .arbeitnow import ArbeitnowSource
from .glassdoor import GlassdoorSource
from .greenhouse import GreenhouseSource
from .indeed import IndeedSource
from .lever import LeverSource
from .linkedin import LinkedInSource
from .placeholder import PlaceholderSource
from .remotive import RemotiveSource
from .stepstone import StepStoneSource

DEFAULT_SOURCES = {
    "agentur": ArbeitsagenturSource,
    "arbeitnow": ArbeitnowSource,
    "glassdoor": GlassdoorSource,
    "indeed": IndeedSource,
    "linkedin": LinkedInSource,
    "remotive": RemotiveSource,
    "stepstone": StepStoneSource,
}

OPTIONAL_COMPANY_SOURCES = {
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
}

PLACEHOLDER_SOURCES = {
    "instaffo": "Requires compliant API/browser implementation; direct scraping is not included.",
}


def build_sources(names: list[str], greenhouse: tuple[str, ...], lever: tuple[str, ...]):
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
    return sources
