from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HostEntry:
    name: str
    target: str
    hostname: str | None = None
    user: str | None = None
    port: int | None = None
    source: str = ""
    source_path: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    favorite: bool = False
    alias: bool = False
    last_used: float | None = None
    usage_count: int = 0

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.name}"
