from datetime import datetime, timedelta, timezone

from canyin_news.selection import select_section


BJ = timezone(timedelta(hours=8), "Asia/Shanghai")
END = datetime(2026, 7, 5, 9, 20, tzinfo=BJ)
START = END - timedelta(days=1)


def item(identifier, hours, score=70):
    return {
        "id": identifier,
        "published_at": END - timedelta(hours=hours),
        "score": score,
    }


def test_incremental_items_win_and_history_is_not_repeated():
    selected = select_section(
        [item("new", 2), item("sent", 3), item("补充", 30)],
        sent_ids={"sent"},
        start=START,
        end=END,
        target=3,
    )

    assert [entry["id"] for entry in selected] == ["new", "补充"]
    assert selected[1]["freshness_label"] == "补充阅读"


def test_zero_incremental_items_become_recent_selection():
    selected = select_section([item("recent", 30)], set(), START, END, 3)

    assert selected[0]["freshness_label"] == "近期精选"
