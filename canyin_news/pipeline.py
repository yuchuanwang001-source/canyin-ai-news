import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from canyin_news.classify import classify_article
from canyin_news.annotations import chinese_note_for_english_title
from canyin_news.models import Article
from canyin_news.render import render_report
from canyin_news.scoring import passes_quality_gate, score_article
from canyin_news.selection import select_section
from canyin_news.sources.legacy import load_legacy_articles
from canyin_news.sources.platform import keep_platform_articles
from canyin_news.sources.food_brands import keep_ka_brand_articles
from canyin_news.sources.rss import fetch_rss
from canyin_news.timeutils import BJ
from canyin_news.dingtalk import send_reserved_to_groups
from canyin_news.state import ReportState


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
    selected_ids: list[str]


WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def _candidate(article: Article, now: datetime) -> tuple[dict, dict] | None:
    category = article.category or classify_article(
        article.title, article.summary, article.source
    )
    raw = asdict(article)
    raw["category"] = category
    raw["zh_note"] = chinese_note_for_english_title(
        article.title, article.source
    )
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
        food_section = category == "餐饮动态"
        sections[title] = select_section(
            pools[category],
            sent_ids,
            start,
            end,
            target=3,
            max_count=5,
            expansion_score=60,
            lookback_hours=168 if food_section else 72,
            empty_label="本周精选" if food_section else "近期精选",
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
        selected_ids=[item["id"] for item in selected],
    )


def collect_configured_sources(config_path: str | Path):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    articles = []
    health = []
    for source in config.get("ai_rss", []):
        fetched, status = fetch_rss(source["name"], source["url"])
        for article in fetched:
            article.category = classify_article(
                article.title, article.summary, article.source
            )
        articles.extend(fetched)
        health.append(asdict(status))
    for source in config.get("platform_rss", []):
        fetched, status = fetch_rss(
            source["name"],
            source["url"],
            forced_category="平台动态",
            use_entry_source=True,
        )
        articles.extend(keep_platform_articles(fetched))
        health.append(asdict(status))
    for source in config.get("food_ka_rss", []):
        fetched, status = fetch_rss(
            source["name"],
            source["url"],
            forced_category="餐饮动态",
            use_entry_source=True,
        )
        articles.extend(keep_ka_brand_articles(fetched))
        health.append(asdict(status))
    return articles, health


def prepare_dry_run(
    *,
    articles_path: str | Path = "articles.json",
    preview_path: str | Path = "report_preview.md",
    config_path: str | Path = "config/sources.json",
    health_path: str | Path = "source_health.json",
    history_path: str | Path = "sent_history.json",
    now: datetime | None = None,
    send_func=None,
) -> ReportBuildResult:
    del send_func
    current = now or datetime.now(BJ)
    legacy = load_legacy_articles(articles_path)
    external, health = collect_configured_sources(config_path)
    history_file = Path(history_path)
    sent_ids = set()
    if history_file.exists():
        history = json.loads(history_file.read_text(encoding="utf-8"))
        sent_ids = set(history.get("articles", {}))
    result = build_report(
        legacy + external,
        sent_ids=sent_ids,
        start=current - timedelta(hours=24),
        end=current,
        date_text=current.strftime("%Y.%m.%d"),
        weekday=WEEKDAYS[current.weekday()],
    )
    Path(preview_path).write_text(result.markdown, encoding="utf-8")
    Path(health_path).write_text(
        json.dumps(health, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _write_state(path, state):
    Path(path).write_text(
        json.dumps(
            {"business_date": state.business_date, "groups": state.groups},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _read_state(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReportState(data["business_date"], data["groups"])


def prepare_production_bundle(
    *,
    articles_path,
    bundle_path,
    state_path,
    preview_path,
    health_path,
    group_names,
    now=None,
):
    current = now or datetime.now(BJ)
    result = prepare_dry_run(
        articles_path=articles_path,
        preview_path=preview_path,
        health_path=health_path,
        now=current,
    )
    content_hash = hashlib.sha256(result.markdown.encode("utf-8")).hexdigest()[:20]
    state = ReportState.empty(current.strftime("%Y-%m-%d"))
    for group in group_names:
        state.reserve(group, content_hash, current)
    _write_state(state_path, state)
    Path(bundle_path).write_text(
        json.dumps(
            {
                "title": f"餐饮AI情报站 · {current.strftime('%Y.%m.%d')}",
                "markdown": result.markdown,
                "selected_ids": result.selected_ids,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def send_production_bundle(
    *,
    bundle_path,
    state_path,
    history_path="sent_history.json",
    groups,
    now=None,
    post_func=None,
):
    current = now or datetime.now(BJ)
    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    state = _read_state(state_path)
    kwargs = {}
    if post_func is not None:
        kwargs["post_func"] = post_func
    try:
        send_reserved_to_groups(
            bundle["markdown"],
            groups,
            state,
            current,
            title=bundle["title"],
            **kwargs,
        )
        history_file = Path(history_path)
        if history_file.exists():
            history = json.loads(history_file.read_text(encoding="utf-8"))
        else:
            history = {"version": 1, "articles": {}}
        for article_id in bundle.get("selected_ids", []):
            history.setdefault("articles", {})[article_id] = {
                "sent_at": current.isoformat(),
                "business_date": state.business_date,
            }
        history_file.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    finally:
        _write_state(state_path, state)
    return state


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    mode = prepare.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--production", action="store_true")
    prepare.add_argument("--articles", default="articles.json")
    prepare.add_argument("--output", default="report_preview.md")
    send = subparsers.add_parser("send")
    send.add_argument("--bundle", default="report_bundle.json")
    send.add_argument("--state", default="report_state.json")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        if args.production:
            group_names = [
                name
                for name, env_name in (
                    ("group_1", "DINGTALK_TOKEN"),
                    ("group_2", "DINGTALK_TOKEN2"),
                )
                if os.environ.get(env_name)
            ]
            if not group_names:
                parser.error("production requires at least one DINGTALK_TOKEN")
            result = prepare_production_bundle(
                articles_path=args.articles,
                bundle_path="report_bundle.json",
                state_path="report_state.json",
                preview_path=args.output,
                health_path="source_health.json",
                group_names=group_names,
            )
        else:
            result = prepare_dry_run(
                articles_path=args.articles,
                preview_path=args.output,
            )
        label = "PRODUCTION bundle" if args.production else "DRY_RUN"
        print(
            f"{label} ready: new={result.new_count}, "
            f"supplement={result.supplement_count}, output={args.output}"
        )
    elif args.command == "send":
        groups = {
            name: token
            for name, token in (
                ("group_1", os.environ.get("DINGTALK_TOKEN")),
                ("group_2", os.environ.get("DINGTALK_TOKEN2")),
            )
            if token
        }
        if not groups:
            parser.error("send requires at least one DINGTALK_TOKEN")
        send_production_bundle(
            bundle_path=args.bundle,
            state_path=args.state,
            groups=groups,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
