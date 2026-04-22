from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchReport:
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)
