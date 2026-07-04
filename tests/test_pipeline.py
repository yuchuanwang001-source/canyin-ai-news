from datetime import datetime, timedelta, timezone

from canyin_news.models import Article, DateConfidence
from canyin_news.pipeline import build_report


BJ = timezone(timedelta(hours=8), "Asia/Shanghai")
END = datetime(2026, 7, 5, 9, 20, tzinfo=BJ)
START = END - timedelta(days=1)


def make_article(identifier, title, source, category, hours):
    return Article(
        id=identifier,
        title=title,
        url=f"https://example.com/{identifier}",
        source=source,
        discovered_at=END,
        published_at=END - timedelta(hours=hours),
        date_confidence=DateConfidence.EXACT,
        summary="这是一条具有经营参考价值的资讯摘要",
        category=category,
    )


def test_build_report_uses_three_sections_and_skips_sent_articles():
    articles = [
        make_article("food", "头部餐饮品牌推出夏季新品", "红餐网", "餐饮动态", 2),
        make_article("platform", "美团上线商家流量新业务", "美团官方", "平台动态", 3),
        make_article("ai", "OpenAI 发布新模型", "OpenAI", "AI行业资讯", 4),
        make_article("sent", "餐饮品牌开出新店", "红餐网", "餐饮动态", 5),
    ]

    result = build_report(articles, {"sent"}, START, END, "2026.07.05", "星期日")

    assert set(result.sections) == {"🍔 餐饮动态", "🛵 平台动态", "🤖 AI行业资讯"}
    assert "头部餐饮品牌推出夏季新品" in result.markdown
    assert "餐饮品牌开出新店" not in result.markdown
    assert result.new_count == 3
