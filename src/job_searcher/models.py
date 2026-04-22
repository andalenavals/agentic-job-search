from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SearchQuery:
    title: str
    location: str | None = None
    remote: bool = False
    limit: int = 25
    include_unverified: bool = False
    greenhouse_companies: tuple[str, ...] = ()
    lever_companies: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobPosting:
    title: str
    company: str
    location: str | None
    source: str
    source_url: str
    apply_url: str | None = None
    description: str | None = None
    published_at: datetime | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def best_url(self) -> str:
        return self.apply_url or self.source_url
