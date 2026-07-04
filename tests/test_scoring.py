from datetime import datetime, timedelta, timezone

from canyin_news.scoring import passes_quality_gate, score_article


NOW = datetime(2026, 7, 5, 9, 20, tzinfo=timezone(timedelta(hours=8)))


def article(**overrides):
    base = {
        "title": "美团上线餐饮商家新流量产品",
        "summary": "面向全国外卖商家开放，将影响流量获取和经营成本",
        "source": "美团官方",
        "category": "平台动态",
        "url": "https://example.com/a",
        "published_at": NOW - timedelta(hours=2),
    }
    base.update(overrides)
    return base


def test_quality_gate_rejects_promotional_content_before_scoring():
    candidate = article(title="火热招商加盟，点击报名")

    assert not passes_quality_gate(candidate)


def test_quality_gate_rejects_unknown_publication_time():
    assert not passes_quality_gate(article(published_at=None))


def test_quality_gate_rejects_mixed_news_roundups():
    candidate = article(title="氪星晚报｜西贝退出；Meta AI投入增加")

    assert not passes_quality_gate(candidate)


def test_score_exposes_six_dimensions_and_total():
    breakdown = score_article(article(), NOW)

    assert breakdown.total >= 60
    assert breakdown.total == min(
        100,
        breakdown.relevance
        + breakdown.impact
        + breakdown.authority
        + breakdown.freshness
        + breakdown.novelty
        + breakdown.actionability
        - breakdown.penalty,
    )


def test_official_high_impact_event_outranks_generic_commentary():
    important = score_article(article(), NOW)
    generic = score_article(
        article(
            title="关于平台经营的一些看法",
            summary="文章讨论行业现象",
            source="未知博客",
        ),
        NOW,
    )

    assert important.total > generic.total
