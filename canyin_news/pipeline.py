from dataclasses import asdict, dataclass
from datetime import datetime

from canyin_news.classify import classify_article
from canyin_news.models import Article
from canyin_news.render import render_report
from canyin_news.scoring import passes_quality_gate, score_article
from canyin_news.selection import select_section


SECTION_CATEGORIES = {
    "🍔 餐饮动态": "餐饮动态",
    "🛵 平台动态": "平台动态",
    "🤖 AI行业资讯": "AI行业资讯",
}


@dataclass(slots=True)
class ReportBuildResult:
    markdown: str
    sections: dict[str, list[dict]]
    score_details: dict[str, dict]
    new_count: int
    supplement_count: int


def _candidate(article: Article, now: datetime) -> tuple[dict, dict] | None:
    category = article.category or classify_article(
        article.title, article.summary, article.source
    )
    raw = asdict(article)
    raw["category"] = category
    if not passes_quality_gate(raw):
        return None
    breakdown = score_article(raw, now)
    raw["score"] = breakdown.total
    return raw, asdict(breakdown)


def build_report(
    articles: list[Article],
    sent_ids: set[str],
    start: datetime,
    end: datetime,
    date_text: str,
    weekday: str,
    budget: int = 3600,
) -> ReportBuildResult:
    pools = {category: [] for category in SECTION_CATEGORIES.values()}
    score_details = {}
    for article in articles:
        prepared = _candidate(article, end)
        if prepared is None:
            continue
        candidate, breakdown = prepared
        pools[candidate["category"]].append(candidate)
        score_details[candidate["id"]] = breakdown

    sections = {}
    for title, category in SECTION_CATEGORIES.items():
        sections[title] = select_section(
            pools[category],
            sent_ids,
            start,
            end,
            target=3,
            max_count=5,
            expansion_score=60,
        )

    markdown = render_report(date_text, weekday, sections, budget)
    selected = [item for items in sections.values() for item in items]
    new_count = sum(not item.get("freshness_label") for item in selected)
    return ReportBuildResult(
        markdown=markdown,
        sections=sections,
        score_details=score_details,
        new_count=new_count,
        supplement_count=len(selected) - new_count,
    )
