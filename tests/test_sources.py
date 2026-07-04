import responses

from canyin_news.models import DateConfidence
from canyin_news.sources.rss import fetch_rss


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
