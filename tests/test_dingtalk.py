from datetime import datetime, timezone

import pytest

from canyin_news.dingtalk import (
    DefiniteSendFailure,
    UncertainSendResult,
    send_to_groups,
)
from canyin_news.state import ReportState


NOW = datetime(2026, 7, 5, 1, 30, tzinfo=timezone.utc)


def test_successful_group_is_marked_sent():
    state = ReportState.empty("2026-07-05")
    calls = []

    send_to_groups(
        "日报正文",
        {"group_1": "token-1"},
        state,
        NOW,
        post_func=lambda token, title, text: calls.append(token) or {"errcode": 0},
    )

    assert calls == ["token-1"]
    assert state.groups["group_1"]["status"] == "sent"


def test_business_error_is_definite_and_can_retry_later():
    state = ReportState.empty("2026-07-05")

    with pytest.raises(DefiniteSendFailure):
        send_to_groups(
            "日报正文",
            {"group_1": "token-1"},
            state,
            NOW,
            post_func=lambda *_: {"errcode": 310000, "errmsg": "keywords not in content"},
        )

    assert state.groups["group_1"]["status"] == "failed"


def test_timeout_is_uncertain_and_blocks_automatic_retry():
    state = ReportState.empty("2026-07-05")

    def timeout(*_):
        raise TimeoutError("read timed out")

    with pytest.raises(UncertainSendResult):
        send_to_groups(
            "日报正文",
            {"group_1": "token-1"},
            state,
            NOW,
            post_func=timeout,
        )

    assert state.groups["group_1"]["status"] == "uncertain"
