from datetime import timedelta


def select_section(items, sent_ids, start, end, target=3):
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
    chosen = fresh[:target]
    for item in chosen:
        item["freshness_label"] = ""

    if len(chosen) >= target:
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
        limit = min(target - len(chosen), max(1, target // 2))
        label = "补充阅读"
    else:
        limit = min(target, 3)
        label = "近期精选"
    for item in recent[:limit]:
        item["freshness_label"] = label
        chosen.append(item)
    return chosen
