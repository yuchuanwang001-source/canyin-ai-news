from dataclasses import dataclass


@dataclass(slots=True)
class SourceHealth:
    source: str
    ok: bool
    elapsed_ms: int
    article_count: int
    valid_date_ratio: float
    error: str = ""
