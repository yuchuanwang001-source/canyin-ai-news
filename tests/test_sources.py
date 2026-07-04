import responses

from canyin_news.models import DateConfidence
from canyin_news.sources.rss import fetch_rss
from canyin_news.sources.platform import keep_platform_articles


@responses.activate
def test_rss_missing_date_does_not_invent_current_time():
    responses.get(
        "https://example.com/feed.xml",
        body="""<?xml version="1.0"?>
        <rss version="2.0"><channel>
        <title>Example Feed</title><link>https://example.com/</link>
        <description>Example</description><item>
        <title>AI update</title><link>https://example.com/a</link>
        </item></channel></rss>""",
        status=200,
        content_type="application/rss+xml",
    )

    result, health = fetch_rss("Example", "https://example.com/feed.xml")

    assert health.ok, health.error
    assert result[0].published_at is None
    assert result[0].date_confidence is DateConfidence.UNKNOWN
    assert health.valid_date_ratio == 0


@responses.activate
def test_rss_reports_http_failure_as_source_health():
    responses.get("https://example.com/feed.xml", status=503)

    result, health = fetch_rss("Example", "https://example.com/feed.xml")

    assert result == []
    assert not health.ok
    assert "503" in health.error


@responses.activate
def test_news_search_rss_preserves_original_publisher_and_category():
    responses.get(
        "https://example.com/platform.xml",
        body="""<?xml version="1.0"?>
        <rss version="2.0"><channel><title>News</title>
        <link>https://example.com/</link><description>News</description><item>
        <title>美团上线餐饮商家新业务 - 财联社</title>
        <link>https://news.example.com/a</link>
        <source url="https://www.cls.cn">财联社</source>
        <pubDate>Sat, 04 Jul 2026 01:20:00 GMT</pubDate>
        </item></channel></rss>""",
        status=200,
        content_type="application/rss+xml",
    )

    result, _ = fetch_rss(
        "平台新闻搜索",
        "https://example.com/platform.xml",
        forced_category="平台动态",
        use_entry_source=True,
    )

    assert result[0].source == "财联社"
    assert result[0].category == "平台动态"


def test_platform_filter_requires_both_platform_entity_and_event():
    matching = type("Item", (), {
        "title": "京东外卖上线商家新业务", "summary": "", "source": "财联社",
        "category": "平台动态",
    })()
    unrelated = type("Item", (), {
        "title": "京东发布新款手机", "summary": "", "source": "科技媒体",
        "category": "平台动态",
    })()

    assert keep_platform_articles([matching, unrelated]) == [matching]
