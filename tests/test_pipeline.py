import json
from datetime import datetime, timedelta, timezone

import pytest

from canyin_news.models import Article, DateConfidence
from canyin_news.pipeline import (
    build_report,
    prepare_dry_run,
    prepare_production_bundle,
    send_production_bundle,
    watchdog_status,
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


def test_build_report_deduplicates_same_event_across_sources():
    articles = [
        make_article(
            "platform-1",
            "抖音生活服务餐饮火锅行业峰会交易增长80%",
            "红餐网",
            "平台动态",
            2,
        ),
        make_article(
            "platform-2",
            "抖音生活服务餐饮火锅行业峰会交易增长80%",
            "中国新闻网",
            "平台动态",
            3,
        ),
    ]

    result = build_report(articles, set(), START, END, "2026.07.05", "星期日")

    assert len(result.sections["🛵 平台动态"]) == 1


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


def test_partial_group_success_still_records_article_history(tmp_path):
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"title":"日报","markdown":"正文","selected_ids":["article-1"]}',
        encoding="utf-8",
    )
    state = tmp_path / "state.json"
    state.write_text(
        '{"business_date":"2026-07-05","groups":{'
        '"group_1":{"status":"sending","content_hash":"x","lease_expires_at":'
        '"2026-07-05T02:00:00+00:00"},'
        '"group_2":{"status":"sending","content_hash":"x","lease_expires_at":'
        '"2026-07-05T02:00:00+00:00"}}}',
        encoding="utf-8",
    )
    history = tmp_path / "history.json"

    def post(token, *_):
        if token == "token-2":
            return {"errcode": 310000, "errmsg": "rejected"}
        return {"errcode": 0}

    with pytest.raises(Exception, match="group_2"):
        send_production_bundle(
            bundle_path=bundle,
            state_path=state,
            history_path=history,
            groups={"group_1": "token-1", "group_2": "token-2"},
            now=END,
            post_func=post,
        )

    saved_state = json.loads(state.read_text(encoding="utf-8"))
    assert saved_state["groups"]["group_1"]["status"] == "sent"
    assert saved_state["groups"]["group_2"]["status"] == "failed"
    saved_history = json.loads(history.read_text(encoding="utf-8"))
    assert saved_history["articles"]["article-1"]["business_date"] == "2026-07-05"


def _write_existing_delivery(tmp_path, groups):
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps(
            {"business_date": "2026-07-05", "groups": groups},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"title":"原日报","markdown":"原正文","selected_ids":["article-1"]}',
        encoding="utf-8",
    )
    articles = tmp_path / "articles.json"
    articles.write_text('{"articles":[]}', encoding="utf-8")
    return articles, bundle, state


def test_fallback_after_both_groups_sent_does_not_send_again(tmp_path, monkeypatch):
    articles, bundle, state = _write_existing_delivery(
        tmp_path,
        {
            "group_1": {"status": "sent"},
            "group_2": {"status": "sent"},
        },
    )
    monkeypatch.setattr(
        "canyin_news.pipeline.collect_configured_sources",
        lambda *_: ([], []),
    )

    prepare_production_bundle(
        articles_path=articles,
        bundle_path=bundle,
        state_path=state,
        preview_path=tmp_path / "preview.md",
        health_path=tmp_path / "health.json",
        group_names=["group_1", "group_2"],
        now=END + timedelta(minutes=27),
    )
    calls = []
    send_production_bundle(
        bundle_path=bundle,
        state_path=state,
        history_path=tmp_path / "history.json",
        groups={"group_1": "token-1", "group_2": "token-2"},
        now=END + timedelta(minutes=27),
        post_func=lambda token, *_: calls.append(token) or {"errcode": 0},
    )

    assert calls == []
    assert json.loads(bundle.read_text(encoding="utf-8"))["markdown"] == "原正文"


def test_fallback_retries_only_failed_group_with_original_bundle(
    tmp_path, monkeypatch
):
    articles, bundle, state = _write_existing_delivery(
        tmp_path,
        {
            "group_1": {"status": "sent"},
            "group_2": {"status": "failed", "error": "rejected"},
        },
    )
    monkeypatch.setattr(
        "canyin_news.pipeline.collect_configured_sources",
        lambda *_: ([], []),
    )

    prepare_production_bundle(
        articles_path=articles,
        bundle_path=bundle,
        state_path=state,
        preview_path=tmp_path / "preview.md",
        health_path=tmp_path / "health.json",
        group_names=["group_1", "group_2"],
        now=END + timedelta(minutes=27),
    )
    calls = []
    send_production_bundle(
        bundle_path=bundle,
        state_path=state,
        history_path=tmp_path / "history.json",
        groups={"group_1": "token-1", "group_2": "token-2"},
        now=END + timedelta(minutes=27),
        post_func=lambda token, *_: calls.append(token) or {"errcode": 0},
    )

    assert calls == ["token-2"]
    assert json.loads(bundle.read_text(encoding="utf-8"))["markdown"] == "原正文"
    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert history["articles"]["article-1"]["business_date"] == "2026-07-05"


def test_fallback_never_retries_uncertain_group(tmp_path, monkeypatch):
    articles, bundle, state = _write_existing_delivery(
        tmp_path,
        {
            "group_1": {"status": "sent"},
            "group_2": {"status": "uncertain", "error": "read timed out"},
        },
    )
    monkeypatch.setattr(
        "canyin_news.pipeline.collect_configured_sources",
        lambda *_: ([], []),
    )

    prepare_production_bundle(
        articles_path=articles,
        bundle_path=bundle,
        state_path=state,
        preview_path=tmp_path / "preview.md",
        health_path=tmp_path / "health.json",
        group_names=["group_1", "group_2"],
        now=END + timedelta(minutes=27),
    )
    calls = []
    send_production_bundle(
        bundle_path=bundle,
        state_path=state,
        history_path=tmp_path / "history.json",
        groups={"group_1": "token-1", "group_2": "token-2"},
        now=END + timedelta(minutes=27),
        post_func=lambda token, *_: calls.append(token) or {"errcode": 0},
    )

    assert calls == []


def test_same_day_state_without_bundle_fails_closed(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    state.write_text(
        '{"business_date":"2026-07-05","groups":'
        '{"group_1":{"status":"sent"},"group_2":{"status":"sent"}}}',
        encoding="utf-8",
    )
    articles = tmp_path / "articles.json"
    articles.write_text('{"articles":[]}', encoding="utf-8")
    monkeypatch.setattr(
        "canyin_news.pipeline.collect_configured_sources",
        lambda *_: ([], []),
    )

    with pytest.raises(RuntimeError, match="bundle"):
        prepare_production_bundle(
            articles_path=articles,
            bundle_path=tmp_path / "missing-bundle.json",
            state_path=state,
            preview_path=tmp_path / "preview.md",
            health_path=tmp_path / "health.json",
            group_names=["group_1", "group_2"],
            now=END + timedelta(minutes=27),
        )

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["groups"]["group_1"]["status"] == "sent"


def test_production_requires_both_group_tokens(monkeypatch):
    monkeypatch.setenv("DINGTALK_TOKEN", "token-1")
    monkeypatch.delenv("DINGTALK_TOKEN2", raising=False)

    from canyin_news.pipeline import main

    with pytest.raises(SystemExit) as exc:
        main(["prepare", "--production"])

    assert exc.value.code == 2


def test_watchdog_is_read_only_and_requires_both_groups_sent(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(
        '{"business_date":"2026-07-05","groups":'
        '{"group_1":{"status":"sent"},"group_2":{"status":"sent"}}}',
        encoding="utf-8",
    )
    before = state.read_bytes()

    assert watchdog_status(state, END) == 0
    assert state.read_bytes() == before

    state.write_text(
        '{"business_date":"2026-07-05","groups":'
        '{"group_1":{"status":"sent"},"group_2":{"status":"failed"}}}',
        encoding="utf-8",
    )
    assert watchdog_status(state, END) == 1
