from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from canyin_news.models import DateConfidence


BJ = timezone(timedelta(hours=8), "Asia/Shanghai")


def parse_published_at(raw: str) -> tuple[datetime | None, DateConfidence]:
    value = (raw or "").strip()
    if not value:
        return None, DateConfidence.UNKNOWN

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        confidence = DateConfidence.EXACT
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            confidence = DateConfidence.EXACT
        except (TypeError, ValueError):
            try:
                parsed = datetime.strptime(value[:10], "%Y-%m-%d")
                confidence = DateConfidence.DATE_ONLY
            except ValueError:
                return None, DateConfidence.UNKNOWN

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BJ)
    return parsed.astimezone(BJ), confidence


def in_incremental_window(
    value: datetime | None,
    start: datetime,
    end: datetime,
) -> bool:
    return value is not None and start < value <= end
