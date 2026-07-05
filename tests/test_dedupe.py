from canyin_news.dedupe import (
    article_fingerprint,
    canonicalize_url,
    event_fingerprint,
)


def test_tracking_parameters_do_not_change_identity():
    left = canonicalize_url("https://example.com/a?utm_source=x&id=7")
    right = canonicalize_url("https://example.com/a?id=7")

    assert left == right


def test_title_fingerprint_ignores_spacing_and_punctuation():
    assert article_fingerprint(
        "OpenAI，发布新模型", "OpenAI"
    ) == article_fingerprint("OpenAI 发布新模型", "OpenAI")


def test_event_fingerprint_matches_same_title_across_sources():
    assert event_fingerprint(
        "抖音生活服务餐饮火锅行业峰会：交易增长80%"
    ) == event_fingerprint(
        "抖音生活服务餐饮火锅行业峰会：交易增长80%"
    )
