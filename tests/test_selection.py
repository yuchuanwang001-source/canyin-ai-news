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
        "source": f"source-{identifier}",
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


def test_three_low_scoring_qualified_items_are_still_selected():
    selected = select_section(
        [item(f"low-{index}", index, score=50) for index in range(1, 6)],
        set(),
        START,
        END,
    )

    assert len(selected) == 3


def test_high_scoring_items_expand_section_to_five():
    selected = select_section(
        [item(f"high-{index}", index, score=70) for index in range(1, 7)],
        set(),
        START,
        END,
    )

    assert len(selected) == 5


def test_same_source_is_limited_to_two_entries():
    candidates = [item(f"same-{index}", index, score=80) for index in range(1, 6)]
    for candidate in candidates:
        candidate["source"] = "同一来源"
    candidates.extend(
        [item("other-1", 6, score=70), item("other-2", 7, score=70)]
    )

    selected = select_section(candidates, set(), START, END)

    assert sum(entry["source"] == "同一来源" for entry in selected) == 2
