SECTION_EMPTY_TEXT = "今日暂无符合标准的新资讯"


def _entry(item: dict, summary_limit: int, index: int) -> str:
    summary = item.get("summary", "").strip()
    if len(summary) > summary_limit:
        summary = summary[: max(0, summary_limit - 1)].rstrip() + "…"
    label = (
        f' · {item["freshness_label"]}'
        if item.get("freshness_label")
        else ""
    )
    number = f"{index}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}"
    body = f'**{number} [{item["title"]}]({item["url"]})**{label}\n'
    if item.get("zh_note"):
        body += f'{item["zh_note"]}\n'
    if summary:
        body += f"{summary}\n"
    return body + f'来源：{item["source"]}\n\n'


def render_report(
    date_text: str,
    weekday: str,
    sections: dict[str, list[dict]],
    new_count: int = 0,
    supplement_count: int = 0,
    budget: int = 3600,
) -> str:
    header = (
        f"## 📡 餐饮AI情报站 · {date_text} {weekday}\n\n"
        "每天3分钟，读懂餐饮圈与AI圈\n\n"
    )
    sources = list(
        dict.fromkeys(
            item["source"]
            for items in sections.values()
            for item in items
            if item.get("source")
        )
    )
    footer = (
        f"来源：{'、'.join(sources) if sources else '暂无'}\n"
        f"本期新增：{new_count} 条｜近期补充：{supplement_count} 条\n"
        f"数据更新时间：{date_text}"
    )
    output = header

    for name, items in sections.items():
        section = f"### {name}\n\n"
        if not items:
            section += f"> {SECTION_EMPTY_TEXT}\n\n"
        for index, item in enumerate(items, 1):
            candidate = _entry(item, 90, index)
            if len(output + section + candidate + footer) > budget:
                candidate = _entry(item, 40, index)
            if len(output + section + candidate + footer) > budget:
                break
            section += candidate
        if len(output + section + footer) <= budget:
            output += section

    result = output + footer
    if len(result) > budget:
        raise ValueError("fixed report structure exceeds markdown budget")
    return result
