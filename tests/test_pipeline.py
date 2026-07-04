from datetime import datetime, timedelta, timezone

from canyin_news.models import Article, DateConfidence
from canyin_news.pipeline import (
    build_report,
    prepare_dry_run,
    prepare_production_bundle,
    send_production_bundle,
)


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


def test_dry_run_writes_preview_without_sending(tmp_path, monkeypatch):
    articles_path = tmp_path / "articles.json"
    articles_path.write_text('{"articles":[]}', encoding="utf-8")
    preview_path = tmp_path / "preview.md"
    send_calls = []
    monkeypatch.setattr(
        "canyin_news.pipeline.collect_configured_sources",
        lambda *_: ([], []),
    )

    result = prepare_dry_run(
        articles_path=articles_path,
        preview_path=preview_path,
        health_path=tmp_path / "health.json",
        now=END,
        send_func=lambda *_: send_calls.append(True),
    )

    assert preview_path.exists()
    assert "餐饮AI情报站" in preview_path.read_text(encoding="utf-8")
    assert send_calls == []
    assert result.new_count == 0


def test_production_bundle_persists_lease_before_mocked_send(tmp_path, monkeypatch):
    articles_path = tmp_path / "articles.json"
    articles_path.write_text('{"articles":[]}', encoding="utf-8")
    monkeypatch.setattr(
        "canyin_news.pipeline.collect_configured_sources",
        lambda *_: ([], []),
    )
    bundle = tmp_path / "bundle.json"
    state = tmp_path / "state.json"
    prepare_production_bundle(
        articles_path=articles_path,
        bundle_path=bundle,
        state_path=state,
        preview_path=tmp_path / "preview.md",
        health_path=tmp_path / "health.json",
        group_names=["group_1"],
        now=END,
    )
    assert '"status": "sending"' in state.read_text(encoding="utf-8")

    send_production_bundle(
        bundle_path=bundle,
        state_path=state,
        history_path=tmp_path / "history.json",
        groups={"group_1": "fake-token"},
        now=END,
        post_func=lambda *_: {"errcode": 0},
    )
    assert '"status": "sent"' in state.read_text(encoding="utf-8")


def test_successful_send_records_selected_articles_in_history(tmp_path):
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"title":"日报","markdown":"正文","selected_ids":["article-1"]}',
        encoding="utf-8",
    )
    state = tmp_path / "state.json"
    state.write_text(
        '{"business_date":"2026-07-05","groups":{"group_1":'
        '{"status":"sending","content_hash":"x","lease_expires_at":'
        '"2026-07-05T02:00:00+00:00"}}}',
        encoding="utf-8",
    )
    history = tmp_path / "history.json"

    send_production_bundle(
        bundle_path=bundle,
        state_path=state,
        history_path=history,
        groups={"group_1": "fake-token"},
        now=END,
        post_func=lambda *_: {"errcode": 0},
    )

    assert "article-1" in history.read_text(encoding="utf-8")
