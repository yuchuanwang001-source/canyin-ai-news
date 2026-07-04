import json
from datetime import datetime
from pathlib import Path

from canyin_news.classify import classify_article
from canyin_news.dedupe import article_fingerprint, canonicalize_url
from canyin_news.models import Article
from canyin_news.timeutils import BJ, parse_published_at


def convert_legacy_article(data: dict) -> Article:
    title = str(data.get("title", "")).strip()
    source = str(data.get("source", "")).strip()
    url = str(data.get("url", "")).strip()
    summary = str(data.get("summary", "") or "").strip()
    published_at, confidence = parse_published_at(str(data.get("time", "") or ""))
    if "mp.weixin.qq.com" in url:
        published_at, confidence = parse_published_at("")
    category = classify_article(title, summary, source)
    return Article(
        id=str(data.get("id") or article_fingerprint(title, source)),
        title=title,
        url=url,
        source=source,
        discovered_at=datetime.now(BJ),
        published_at=published_at,
        date_confidence=confidence,
        summary=summary,
        category=category,
        score=int(data.get("score", 0) or 0),
        canonical_url=canonicalize_url(url),
        tags=list(data.get("tags", []) or []),
    )


def load_legacy_articles(path: str | Path) -> list[Article]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        convert_legacy_article(item)
        for item in payload.get("articles", [])
        if item.get("title") and item.get("url")
    ]
