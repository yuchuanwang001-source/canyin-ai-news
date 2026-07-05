import responses
from datetime import datetime, timedelta, timezone

from canyin_news.models import DateConfidence
from canyin_news.sources.aihot import fetch_aihot_selected
from canyin_news.sources.rss import fetch_rss
from canyin_news.sources.platform import keep_platform_articles
from canyin_news.sources.food_brands import keep_ka_brand_articles


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


def test_ka_filter_requires_brand_and_business_action():
    matching = type("Item", (), {
        "title": "瑞幸推出夏季新品菜单", "summary": "", "source": "红餐网",
        "category": None,
    })()
    unrelated = type("Item", (), {
        "title": "瑞幸创始人的个人故事", "summary": "", "source": "自媒体",
        "category": None,
    })()

    assert keep_ka_brand_articles([matching, unrelated]) == [matching]


@responses.activate
def test_aihot_fetches_only_recent_selected_items_with_original_sources():
    responses.get(
        "https://aihot.virxact.com/api/public/items",
        json={
            "items": [
                {
                    "id": "cm9abc456def789ghi012jkl3",
                    "title": "新模型发布",
                    "url": "https://example.com/model",
                    "source": "Anthropic Newsroom",
                    "publishedAt": "2026-07-05T01:00:00.000Z",
                    "summary": "模型能力更新",
                    "category": "ai-models",
                }
            ]
        },
        status=200,
    )
    now = datetime(2026, 7, 5, 9, 20, tzinfo=timezone(timedelta(hours=8)))

    result, health = fetch_aihot_selected(now=now)

    request = responses.calls[0].request
    assert "mode=selected" in request.url
    assert "take=50" in request.url
    assert "since=" in request.url
    assert health.ok
    assert result[0].source == "Anthropic Newsroom"
    assert result[0].category == "AI行业资讯"
    assert result[0].tags == ["AIHOT精选"]


@responses.activate
def test_aihot_uses_curated_rss_when_primary_api_is_unavailable():
    responses.get(
        "https://aihot.virxact.com/api/public/items",
        status=503,
    )
    responses.get(
        "https://aihot.tech/feed.xml",
        body="""<?xml version="1.0"?>
        <rss version="2.0"><channel><title>AI Hot</title>
        <link>https://aihot.tech</link><description>Curated</description>
        <item><title>Anthropic releases a new Claude model</title>
        <link>https://example.com/claude</link>
        <description>New AI model</description>
        <pubDate>Sat, 04 Jul 2026 18:00:05 GMT</pubDate></item>
        <item><title>Verizon changes its watch service</title>
        <link>https://example.com/watch</link>
        <description>Telecom update</description>
        <pubDate>Sat, 04 Jul 2026 17:00:05 GMT</pubDate></item>
        </channel></rss>""",
        status=200,
        content_type="application/rss+xml",
    )

    result, health = fetch_aihot_selected(
        fallback_url="https://aihot.tech/feed.xml"
    )

    assert health.ok
    assert "fallback" in health.error
    assert [item.title for item in result] == [
        "Anthropic releases a new Claude model"
    ]
    assert result[0].tags == ["AIHOT精选"]
