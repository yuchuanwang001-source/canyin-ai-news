from datetime import datetime, timedelta, timezone

from canyin_news.models import DateConfidence
from canyin_news.timeutils import in_incremental_window, parse_published_at


BJ = timezone(timedelta(hours=8), "Asia/Shanghai")


def test_missing_date_stays_unknown():
    parsed, confidence = parse_published_at("")

    assert parsed is None
    assert confidence is DateConfidence.UNKNOWN


def test_offset_is_converted_instead_of_replaced():
    parsed, confidence = parse_published_at("2026-07-04T01:20:00+00:00")

    assert parsed == datetime(2026, 7, 4, 9, 20, tzinfo=BJ)
    assert confidence is DateConfidence.EXACT


def test_incremental_window_is_left_open_and_right_closed():
    start = datetime(2026, 7, 4, 9, 20, tzinfo=BJ)
    end = datetime(2026, 7, 5, 9, 20, tzinfo=BJ)

    assert not in_incremental_window(start, start, end)
    assert in_incremental_window(end, start, end)
