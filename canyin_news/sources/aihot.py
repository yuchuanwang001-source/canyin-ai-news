from datetime import datetime, timedelta, timezone
from time import monotonic

import requests

from canyin_news.classify import classify_article
from canyin_news.dedupe import article_fingerprint, canonicalize_url
from canyin_news.models import Article
from canyin_news.sources.base import SourceHealth
from canyin_news.sources.rss import fetch_rss
from canyin_news.timeutils import BJ, parse_published_at


def fetch_aihot_selected(
    *,
    url: str = "https://aihot.virxact.com/api/public/items",
    mode: str = "selected",
    take: int = 50,
    fallback_url: str | None = None,
    now: datetime | None = None,
    timeout: tuple[int, int] = (3, 10),
) -> tuple[list[Article], SourceHealth]:
    started = monotonic()
    current = now or datetime.now(BJ)
    since = (current - timedelta(hours=24)).astimezone(timezone.utc)
    try:
        response = requests.get(
            url,
            params={
                "mode": mode,
                "since": since.isoformat().replace("+00:00", "Z"),
                "take": take,
            },
            timeout=timeout,
            headers={"User-Agent": "canyin-ai-news/1.0"},
        )
        response.raise_for_status()
        discovered_at = datetime.now(BJ)
        articles = []
        valid_dates = 0
        for item in response.json().get("items", []):
            title = str(item.get("title", "")).strip()
            link = str(item.get("url", "")).strip()
            source = str(item.get("source", "")).strip() or "AIHOT"
            if not title or not link:
                continue
            published_at, confidence = parse_published_at(
                str(item.get("publishedAt", "") or "")
            )
            valid_dates += published_at is not None
            articles.append(
                Article(
                    id=str(item.get("id") or article_fingerprint(title, source)),
                    title=title,
                    url=link,
                    source=source,
                    discovered_at=discovered_at,
                    published_at=published_at,
                    date_confidence=confidence,
                    summary=str(item.get("summary", "") or "")[:500],
                    category="AI行业资讯",
                    canonical_url=canonicalize_url(link),
                    tags=["AIHOT精选"],
                )
            )
        elapsed_ms = round((monotonic() - started) * 1000)
        return articles, SourceHealth(
            source="AIHOT精选",
            ok=True,
            elapsed_ms=elapsed_ms,
            article_count=len(articles),
            valid_date_ratio=(
                valid_dates / len(articles) if articles else 0.0
            ),
        )
    except Exception as exc:
        if fallback_url:
            articles, health = fetch_rss(
                "AIHOT精选",
                fallback_url,
                timeout=timeout,
                forced_category="AI行业资讯",
            )
            if health.ok:
                articles = [
                    article
                    for article in articles
                    if classify_article(
                        article.title, article.summary, article.source
                    )
                    == "AI行业资讯"
                ]
                for article in articles:
                    article.tags = ["AIHOT精选"]
                health.article_count = len(articles)
                health.valid_date_ratio = (
                    sum(item.published_at is not None for item in articles)
                    / len(articles)
                    if articles
                    else 0.0
                )
                health.error = f"primary unavailable; RSS fallback active: {exc}"
                return articles, health
        elapsed_ms = round((monotonic() - started) * 1000)
        return [], SourceHealth(
            source="AIHOT精选",
            ok=False,
            elapsed_ms=elapsed_ms,
            article_count=0,
            valid_date_ratio=0.0,
            error=str(exc),
        )
