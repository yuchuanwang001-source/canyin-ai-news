import re


def chinese_note_for_english_title(title: str, source: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", title):
        return ""
    partnership = re.match(
        r"(.+?)\s+and\s+(.+?)\s+announce.*research partnership",
        title,
        flags=re.IGNORECASE,
    )
    if partnership:
        return (
            f"中文注释：{partnership.group(1)} 与 {partnership.group(2)}"
            " 宣布开展新的研究合作，具体信息以官方原文为准。"
        )
    lowered = title.lower()
    if "research" in lowered:
        topic = "发布了一项新的 AI 研究动态"
    elif any(word in lowered for word in ("model", "introducing", "launch", "release")):
        topic = "发布了新的 AI 模型或产品动态"
    elif "partnership" in lowered:
        topic = "宣布了新的合作动态"
    else:
        topic = "发布了一项新的 AI 行业动态"
    return f"中文注释：{source} {topic}，具体信息以官方原文为准。"
