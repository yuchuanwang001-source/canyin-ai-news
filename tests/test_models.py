from datetime import datetime, timezone

from canyin_news.models import Article, DateConfidence


def test_article_keeps_unknown_publication_time_explicit():
    article = Article(
        id="a1",
        title="测试",
        url="https://example.com/a1",
        source="测试源",
        discovered_at=datetime(2026, 7, 4, tzinfo=timezone.utc),
        published_at=None,
        date_confidence=DateConfidence.UNKNOWN,
    )

    assert article.published_at is None
    assert article.date_confidence is DateConfidence.UNKNOWN
