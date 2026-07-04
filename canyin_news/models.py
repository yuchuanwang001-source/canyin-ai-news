from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class DateConfidence(StrEnum):
    EXACT = "exact"
    DATE_ONLY = "date_only"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Article:
    id: str
    title: str
    url: str
    source: str
    discovered_at: datetime
    published_at: datetime | None
    date_confidence: DateConfidence
    summary: str = ""
    category: str | None = None
    score: int = 0
    canonical_url: str = ""
    tags: list[str] = field(default_factory=list)
