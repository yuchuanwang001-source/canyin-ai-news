from canyin_news.dedupe import article_fingerprint, canonicalize_url


def test_tracking_parameters_do_not_change_identity():
    left = canonicalize_url("https://example.com/a?utm_source=x&id=7")
    right = canonicalize_url("https://example.com/a?id=7")

    assert left == right


def test_title_fingerprint_ignores_spacing_and_punctuation():
    assert article_fingerprint(
        "OpenAI，发布新模型", "OpenAI"
    ) == article_fingerprint("OpenAI 发布新模型", "OpenAI")
