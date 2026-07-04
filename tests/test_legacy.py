from canyin_news.models import DateConfidence
from canyin_news.sources.legacy import convert_legacy_article


def test_legacy_platform_category_is_renamed_and_time_is_parsed():
    article = convert_legacy_article(
        {
            "id": "p1",
            "title": "美团上线商家新业务",
            "url": "https://example.com/p1",
            "source": "红餐网",
            "time": "2026-07-04T12:00:00+08:00",
            "summary": "面向餐饮商家",
            "category": "平台政策",
        }
    )

    assert article.category == "平台动态"
    assert article.published_at.isoformat() == "2026-07-04T12:00:00+08:00"


def test_legacy_missing_time_remains_unknown():
    article = convert_legacy_article(
        {
            "title": "一条时间未知的文章",
            "url": "https://example.com/unknown",
            "source": "红餐网",
        }
    )

    assert article.published_at is None
    assert article.date_confidence is DateConfidence.UNKNOWN


def test_legacy_category_is_recomputed_instead_of_trusted():
    article = convert_legacy_article(
        {
            "title": "脆皮中年人，集体过上三无生活",
            "url": "https://example.com/unrelated",
            "source": "36氪AI",
            "time": "2026-07-04T12:00:00+08:00",
            "summary": "无糖可乐、无因咖啡、无醇啤酒",
            "category": "餐饮动态",
        }
    )

    assert article.category is None


def test_historical_exa_time_is_not_treated_as_verified_publication_time():
    article = convert_legacy_article(
        {
            "title": "一篇公众号历史文章",
            "url": "https://mp.weixin.qq.com/s/example",
            "source": "智谱AI",
            "time": "2026-07-04T12:34:56.123456+08:00",
            "category": "AI动态",
        }
    )

    assert article.published_at is None
    assert article.date_confidence is DateConfidence.UNKNOWN
