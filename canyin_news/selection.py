from datetime import timedelta


def _append_diverse(chosen, candidates, limit, minimum_score=45):
    source_counts = {}
    event_ids = set()
    for item in chosen:
        source = item.get("source")
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1
        event_ids.add(item.get("event_id", item["id"]))

    for item in candidates:
        if len(chosen) >= limit or item.get("score", 0) < minimum_score:
            break
        source = item.get("source")
        event_id = item.get("event_id", item["id"])
        if event_id in event_ids:
            continue
        if source and source_counts.get(source, 0) >= 2:
            continue
        chosen.append(item)
        event_ids.add(event_id)
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1
    return chosen


def select_section(
    items,
    sent_ids,
    start,
    end,
    target=3,
    max_count=5,
    expansion_score=60,
):
    usable = [
        item.copy()
        for item in items
        if item["id"] not in sent_ids and item.get("published_at") is not None
    ]
    fresh = sorted(
        (item for item in usable if start < item["published_at"] <= end),
        key=lambda item: (item.get("score", 0), item["published_at"]),
        reverse=True,
    )
    chosen = _append_diverse([], fresh, target)
    for item in chosen:
        item["freshness_label"] = ""

    if len(chosen) >= target:
        expansion = [
            item for item in fresh if item not in chosen and item.get("score", 0) >= expansion_score
        ]
        _append_diverse(chosen, expansion, max_count, expansion_score)
        return chosen

    recent = sorted(
        (
            item
            for item in usable
            if end - timedelta(hours=72) <= item["published_at"] <= start
        ),
        key=lambda item: (item.get("score", 0), item["published_at"]),
        reverse=True,
    )
    if chosen:
        limit = target
        label = "补充阅读"
    else:
        limit = min(target, 3)
        label = "近期精选"
    before = len(chosen)
    _append_diverse(chosen, recent, limit)
    for item in chosen[before:]:
        item["freshness_label"] = label
    return chosen
