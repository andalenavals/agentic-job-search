from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchReport:
    warnings: list[str] = field(default_factory=list)
    seen: int = 0
    accepted: int = 0
    filtered_unverified: int = 0
    filtered_duplicates: int = 0
    filtered_duplicate_links: int = 0
    filtered_duplicate_positions: int = 0

    def warn(self, message: str) -> None:
        self.warnings.append(message)
