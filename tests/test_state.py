from datetime import datetime, timedelta, timezone

import pytest

from canyin_news.state import AutomaticRetryBlocked, ReportState


NOW = datetime(2026, 7, 5, 1, 20, tzinfo=timezone.utc)


def test_sent_group_is_never_reserved_again():
    state = ReportState.empty("2026-07-05")
    state.reserve("group_1", "hash", NOW)
    state.mark_sent("group_1", NOW)

    with pytest.raises(AutomaticRetryBlocked):
        state.reserve("group_1", "hash", NOW + timedelta(minutes=30))


def test_expired_sending_lease_becomes_uncertain():
    state = ReportState.empty("2026-07-05")
    state.reserve("group_1", "hash", NOW, lease_minutes=15)
    state.expire_leases(NOW + timedelta(minutes=16))

    assert state.groups["group_1"]["status"] == "uncertain"
