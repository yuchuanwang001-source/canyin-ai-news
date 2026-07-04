from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/daily-report.yml")


def test_workflow_has_fallback_and_read_only_watchdog_modes():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    options = workflow[True]["workflow_dispatch"]["inputs"]["mode"]["options"]

    assert options == ["dry-run", "production", "watchdog"]
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m canyin_news.pipeline watchdog" in text
    assert "inputs.mode == 'watchdog'" in text


def test_workflow_persists_bundle_and_retries_safe_pushes():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "report_bundle.json" in text
    assert ".github/scripts/persist-report-state.sh" in text
