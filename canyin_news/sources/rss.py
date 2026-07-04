from datetime import datetime
from time import monotonic

import feedparser
import requests
from bs4 import BeautifulSoup

from canyin_news.dedupe import article_fingerprint, canonicalize_url
from canyin_news.models import Article
from canyin_news.sources.base import SourceHealth
from canyin_news.timeutils import BJ, parse_published_at


def fetch_rss(
    source: str,
    url: str,
    *,
    timeout: tuple[int, int] = (3, 10),
    forced_category: str | None = None,
    use_entry_source: bool = False,
) -> tuple[list[Article], SourceHealth]:
    started = monotonic()
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "canyin-ai-news/1.0"},
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        discovered_at = datetime.now(BJ)
        articles = []
        valid_dates = 0
        for entry in feed.entries:
            title = str(entry.get("title", "")).strip()
            link = str(entry.get("link", "")).strip()
            if not title or not link:
                continue
            item_source = source
            if use_entry_source:
                source_data = entry.get("source") or {}
                item_source = str(source_data.get("title") or source).strip()
                suffix = f" - {item_source}"
                if title.endswith(suffix):
                    title = title[: -len(suffix)].strip()
            raw_date = entry.get("published") or entry.get("updated") or ""
            published_at, confidence = parse_published_at(raw_date)
            valid_dates += published_at is not None
            raw_summary = str(entry.get("summary", "") or "")
            summary = BeautifulSoup(raw_summary, "html.parser").get_text(
                " ", strip=True
            )
            canonical_url = canonicalize_url(link)
            articles.append(
                Article(
                    id=article_fingerprint(title, item_source),
                    title=title,
                    url=link,
                    source=item_source,
                    discovered_at=discovered_at,
                    published_at=published_at,
                    date_confidence=confidence,
                    summary=summary[:500],
                    category=forced_category,
                    canonical_url=canonical_url,
                )
            )
        elapsed_ms = round((monotonic() - started) * 1000)
        ratio = valid_dates / len(articles) if articles else 0.0
        return articles, SourceHealth(
            source=source,
            ok=True,
            elapsed_ms=elapsed_ms,
            article_count=len(articles),
            valid_date_ratio=ratio,
        )
    except Exception as exc:
        elapsed_ms = round((monotonic() - started) * 1000)
        return [], SourceHealth(
            source=source,
            ok=False,
            elapsed_ms=elapsed_ms,
            article_count=0,
            valid_date_ratio=0.0,
            error=str(exc),
        )
