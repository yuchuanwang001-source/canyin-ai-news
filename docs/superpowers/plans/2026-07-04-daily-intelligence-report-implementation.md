# 餐饮 AI 情报站日报重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有日报重构为免费、多信源、按增量窗口选稿、逐群防重复，并由 Cloudflare 主调度和 GitHub 兜底调度驱动的生产系统。

**Architecture:** Python 包负责采集、标准化、分类、选稿、渲染、状态机和钉钉发送；GitHub Actions 负责持久化数据与发送状态；Cloudflare Worker 只触发 GitHub workflow。旧脚本保留为兼容入口，但不再拥有业务逻辑。

**Tech Stack:** Python 3.11、pytest、requests、BeautifulSoup、feedparser、GitHub Actions、Cloudflare Workers、Node.js 内置测试运行器。

---

## 文件结构

新建：

```text
canyin_news/
  __init__.py
  models.py          # 标准文章、来源健康和发送状态数据结构
  timeutils.py       # 时区、发布时间解析和增量窗口
  classify.py        # 三板块分类及排除规则
  scoring.py         # 质量门槛和可解释六维重要性评分
  dedupe.py          # URL、标题和事件去重
  selection.py       # 增量选稿、48/72 小时补位
  render.py          # 钉钉 Markdown 字符预算
  state.py           # 逐日逐群发送状态机和租约
  dingtalk.py        # 钉钉传输层
  sources/
    __init__.py
    base.py          # 来源统一接口
    rss.py           # 通用 RSS 适配器
    legacy.py        # 现有红餐、36氪和 Exa 采集适配
    aihot.py         # AIHOT 可选适配器
  pipeline.py        # prepare/send/watchdog 命令入口
config/
  sources.json       # 生产来源配置
tests/
  fixtures/          # 固定输入样本
  test_timeutils.py
  test_classify.py
  test_dedupe.py
  test_selection.py
  test_render.py
  test_state.py
  test_sources.py
  test_pipeline.py
cloudflare-trigger/
  src/index.mjs
  test/index.test.mjs
  wrangler.jsonc
.github/workflows/daily-report.yml
requirements-dev.txt
report_state.json
sent_history.json
```

修改：

```text
scraper.py
scripts/dingtalk_report.py
.github/workflows/daily-update.yml
.github/workflows/dingtalk-report.yml
.gitignore
README.md
```

## 里程碑一：正确性、安全测试和发送幂等

### Task 1：同步线上状态并建立隔离分支

**Files:**
- Preserve: all untracked `_push*.py`, `_trigger.py`, `_test_classify.py`
- Preserve: `__pycache__/`, `scripts/__pycache__/`
- Branch: `codex/daily-report-rebuild`

- [ ] **Step 1: 记录当前工作区和线上提交**

Run:

```powershell
git status --short
git log -3 --oneline
gh api repos/yuchuanwang001-source/canyin-ai-news/commits/main --jq .sha
```

Expected: 输出本地提交、所有未跟踪文件和线上 `main` SHA；不修改任何文件。

- [ ] **Step 2: 获取线上 main**

Run:

```powershell
git fetch origin main
```

Expected: `origin/main` 更新到线上当前提交。

- [ ] **Step 3: 从线上 main 创建隔离工作树**

Run:

```powershell
git worktree add ..\canyin-ai-news-rebuild -b codex/daily-report-rebuild origin/main
```

Expected: 新工作树干净，原工作区的未跟踪文件不受影响。

- [ ] **Step 4: 把两次设计提交移入新分支**

Run:

```powershell
git cherry-pick ca5db40 484bc83
```

Expected: 设计文档存在，新分支基于最新线上代码。

- [ ] **Step 5: 验证隔离状态**

Run:

```powershell
git status --short
git log -4 --oneline
```

Expected: 工作树干净；日志同时包含线上最新提交和两次设计提交。

### Task 2：建立测试框架和标准数据模型

**Files:**
- Create: `requirements-dev.txt`
- Create: `canyin_news/__init__.py`
- Create: `canyin_news/models.py`
- Create: `tests/test_models.py`
- Modify: `.gitignore`

- [ ] **Step 1: 写数据模型失败测试**

```python
from datetime import datetime, timezone
from canyin_news.models import Article, DateConfidence


def test_article_requires_published_at_to_match_confidence():
    article = Article(
        id="a1",
        title="测试",
        url="https://example.com/a1",
        source="测试源",
        discovered_at=datetime(2026, 7, 4, tzinfo=timezone.utc),
        published_at=None,
        date_confidence=DateConfidence.UNKNOWN,
    )
    assert article.published_at is None
    assert article.date_confidence is DateConfidence.UNKNOWN
```

- [ ] **Step 2: 运行并确认失败**

Run:

```powershell
python -m pytest tests/test_models.py -v
```

Expected: FAIL，提示 `canyin_news.models` 不存在。

- [ ] **Step 3: 实现最小标准模型**

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class DateConfidence(StrEnum):
    EXACT = "exact"
    DATE_ONLY = "date_only"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Article:
    id: str
    title: str
    url: str
    source: str
    discovered_at: datetime
    published_at: datetime | None
    date_confidence: DateConfidence
    summary: str = ""
    category: str | None = None
    score: int = 0
    canonical_url: str = ""
    tags: list[str] = field(default_factory=list)
```

Add to `requirements-dev.txt`:

```text
pytest>=8.0,<9
responses>=0.25,<1
PyYAML>=6.0,<7
```

Add to `.gitignore`:

```text
__pycache__/
*.pyc
.pytest_cache/
.coverage
report_preview.md
report_bundle.json
```

- [ ] **Step 4: 运行测试**

Run:

```powershell
python -m pytest tests/test_models.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add requirements-dev.txt .gitignore canyin_news tests/test_models.py
git commit -m "test: add report pipeline model foundation"
```

### Task 3：修复时间语义并实现增量窗口

**Files:**
- Create: `canyin_news/timeutils.py`
- Test: `tests/test_timeutils.py`

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from canyin_news.timeutils import parse_published_at, in_incremental_window

BJ = ZoneInfo("Asia/Shanghai")


def test_missing_date_stays_unknown():
    parsed, confidence = parse_published_at("")
    assert parsed is None
    assert confidence == "unknown"


def test_offset_is_converted_not_replaced():
    parsed, confidence = parse_published_at("2026-07-04T01:20:00+00:00")
    assert parsed == datetime(2026, 7, 4, 9, 20, tzinfo=BJ)
    assert confidence == "exact"


def test_incremental_window_is_left_open_right_closed():
    start = datetime(2026, 7, 4, 9, 20, tzinfo=BJ)
    end = datetime(2026, 7, 5, 9, 20, tzinfo=BJ)
    assert not in_incremental_window(start, start, end)
    assert in_incremental_window(end, start, end)
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/test_timeutils.py -v`

Expected: FAIL，函数尚不存在。

- [ ] **Step 3: 实现时间解析**

```python
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from canyin_news.models import DateConfidence

BJ = ZoneInfo("Asia/Shanghai")


def parse_published_at(raw: str):
    value = (raw or "").strip()
    if not value:
        return None, DateConfidence.UNKNOWN
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        confidence = DateConfidence.EXACT
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            confidence = DateConfidence.EXACT
        except (TypeError, ValueError):
            try:
                parsed = datetime.strptime(value[:10], "%Y-%m-%d")
                confidence = DateConfidence.DATE_ONLY
            except ValueError:
                return None, DateConfidence.UNKNOWN
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BJ)
    return parsed.astimezone(BJ), confidence


def in_incremental_window(value, start, end):
    return value is not None and start < value <= end
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_timeutils.py -v`

Expected: 3 tests PASS。

- [ ] **Step 5: 提交**

```powershell
git add canyin_news/timeutils.py tests/test_timeutils.py
git commit -m "fix: preserve publication time semantics"
```

### Task 4：实现三板块分类

**Files:**
- Create: `canyin_news/classify.py`
- Create: `tests/fixtures/classification_cases.json`
- Test: `tests/test_classify.py`

- [ ] **Step 1: 创建固定样本**

`tests/fixtures/classification_cases.json`:

```json
[
  {"title":"霸王茶姬推出夏季新品","summary":"更新产品矩阵","source":"红餐网","expected":"餐饮动态"},
  {"title":"美团上线餐饮商家新流量产品","summary":"面向外卖商家开放","source":"36氪","expected":"平台动态"},
  {"title":"京东外卖与海底捞达成合作","summary":"即时零售合作","source":"36氪","expected":"平台动态"},
  {"title":"OpenAI 发布新模型","summary":"模型能力更新","source":"OpenAI","expected":"AI行业资讯"},
  {"title":"食品公司注册资本增加","summary":"工商信息变更","source":"36氪","expected":null},
  {"title":"火热招商加盟","summary":"点击报名","source":"未知来源","expected":null}
]
```

- [ ] **Step 2: 写参数化失败测试**

```python
import json
from pathlib import Path
import pytest
from canyin_news.classify import classify_article

CASES = json.loads(Path("tests/fixtures/classification_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES)
def test_classification_cases(case):
    assert classify_article(case["title"], case["summary"], case["source"]) == case["expected"]
```

- [ ] **Step 3: 运行并确认失败**

Run: `python -m pytest tests/test_classify.py -v`

Expected: FAIL，分类模块不存在。

- [ ] **Step 4: 实现来源、实体事件组合和排除规则**

```python
LOW_VALUE = ("招商", "加盟", "报名", "点击领取", "注册资本")
PLATFORMS = ("美团", "饿了么", "淘宝闪购", "京东外卖", "京东秒送", "抖音生活服务")
PLATFORM_EVENTS = ("上线", "合作", "补贴", "佣金", "规则", "流量", "配送", "战略", "组织调整", "新业务")
AI_SOURCES = ("OpenAI", "Anthropic", "Google DeepMind", "Hugging Face", "NVIDIA", "Microsoft Research")
AI_EVENTS = ("AI", "模型", "大模型", "智能体", "Agent", "人工智能")
FOOD_SOURCES = ("红餐网", "餐饮老板内参", "餐企老板内参", "餐饮O2O", "窄门餐眼")
FOOD_EVENTS = ("新品", "菜单", "新店", "餐饮品牌", "门店", "连锁", "出海", "供应链", "会员")


def classify_article(title: str, summary: str, source: str):
    text = f"{title} {summary}"
    if any(word in text for word in LOW_VALUE):
        return None
    if any(entity in text for entity in PLATFORMS) and any(event in text for event in PLATFORM_EVENTS):
        return "平台动态"
    if source in AI_SOURCES or any(word in text for word in AI_EVENTS):
        return "AI行业资讯"
    if source in FOOD_SOURCES or any(word in text for word in FOOD_EVENTS):
        return "餐饮动态"
    return None
```

- [ ] **Step 5: 运行测试并提交**

Run: `python -m pytest tests/test_classify.py -v`

Expected: all cases PASS。

```powershell
git add canyin_news/classify.py tests
git commit -m "feat: define three report categories"
```

### Task 5：实现事件去重和发送历史

**Files:**
- Create: `canyin_news/dedupe.py`
- Create: `sent_history.json`
- Test: `tests/test_dedupe.py`

- [ ] **Step 1: 写失败测试**

```python
from canyin_news.dedupe import canonicalize_url, article_fingerprint


def test_tracking_parameters_do_not_change_identity():
    left = canonicalize_url("https://example.com/a?utm_source=x&id=7")
    right = canonicalize_url("https://example.com/a?id=7")
    assert left == right


def test_title_fingerprint_ignores_spacing_and_punctuation():
    assert article_fingerprint("OpenAI，发布新模型", "OpenAI") == article_fingerprint("OpenAI 发布新模型", "OpenAI")
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/test_dedupe.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现规范化**

```python
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "spm", "from"}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k not in TRACKING))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def article_fingerprint(title: str, source: str) -> str:
    normalized = re.sub(r"[\W_]+", "", title, flags=re.UNICODE).lower()
    return hashlib.sha256(f"{source}|{normalized}".encode()).hexdigest()[:20]
```

Initialize `sent_history.json`:

```json
{"version":1,"articles":{}}
```

- [ ] **Step 4: 运行测试并提交**

Run: `python -m pytest tests/test_dedupe.py -v`

Expected: PASS。

```powershell
git add canyin_news/dedupe.py tests/test_dedupe.py sent_history.json
git commit -m "feat: add stable article identity"
```

### Task 6：实现增量选稿与补位

**Files:**
- Create: `canyin_news/scoring.py`
- Create: `canyin_news/selection.py`
- Test: `tests/test_scoring.py`
- Test: `tests/test_selection.py`

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from canyin_news.selection import select_section

BJ = ZoneInfo("Asia/Shanghai")
END = datetime(2026, 7, 5, 9, 20, tzinfo=BJ)
START = END - timedelta(days=1)


def item(identifier, hours, score=70):
    return {"id": identifier, "published_at": END - timedelta(hours=hours), "score": score}


def test_incremental_items_win_and_history_is_not_repeated():
    selected = select_section(
        [item("new", 2), item("sent", 3), item("补充", 30)],
        sent_ids={"sent"},
        start=START,
        end=END,
        target=3,
    )
    assert [x["id"] for x in selected] == ["new", "补充"]
    assert selected[1]["freshness_label"] == "补充阅读"


def test_zero_incremental_items_become_recent_selection():
    selected = select_section([item("recent", 30)], set(), START, END, 3)
    assert selected[0]["freshness_label"] == "近期精选"


def test_three_qualified_items_below_sixty_are_still_selected():
    selected = select_section(
        [item(f"low-{index}", index, score=50) for index in range(1, 6)],
        set(), START, END,
    )
    assert len(selected) == 3


def test_sixty_plus_items_can_expand_section_to_five():
    selected = select_section(
        [item(f"high-{index}", index, score=70) for index in range(1, 7)],
        set(), START, END,
    )
    assert len(selected) == 5
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/test_selection.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现选择器**

```python
from datetime import timedelta


def select_section(items, sent_ids, start, end, target=3, max_count=5):
    usable = [x.copy() for x in items if x["id"] not in sent_ids and x.get("published_at")]
    fresh = sorted(
        (x for x in usable if start < x["published_at"] <= end),
        key=lambda x: (x["score"], x["published_at"]),
        reverse=True,
    )
    eligible = [row for row in fresh if row["score"] >= 45]
    chosen = eligible[:target]
    for row in chosen:
        row["freshness_label"] = ""
    if len(chosen) >= target:
        chosen.extend(
            row for row in eligible[target:]
            if row["score"] >= 60
        )
        chosen = chosen[:max_count]
        return chosen
    recent = sorted(
        (x for x in usable if end - timedelta(hours=72) <= x["published_at"] <= start),
        key=lambda x: (x["score"], x["published_at"]),
        reverse=True,
    )
    limit = target - len(chosen) if chosen else min(target, 3)
    for row in [item for item in recent if item["score"] >= 45][:limit]:
        row["freshness_label"] = "补充阅读" if chosen else "近期精选"
        chosen.append(row)
    return chosen
```

- [ ] **Step 4: 运行测试并提交**

Run: `python -m pytest tests/test_selection.py -v`

Expected: PASS。

```powershell
git add canyin_news/selection.py tests/test_selection.py
git commit -m "feat: select unseen incremental report content"
```

### Task 7：实现逐群发送状态机

**Files:**
- Create: `canyin_news/state.py`
- Create: `report_state.json`
- Test: `tests/test_state.py`

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime, timedelta, timezone
import pytest
from canyin_news.state import ReportState, AutomaticRetryBlocked

NOW = datetime(2026, 7, 5, 1, 20, tzinfo=timezone.utc)


def test_sent_group_is_never_reserved_again():
    state = ReportState.empty("2026-07-05")
    state.reserve("group_1", "hash", NOW)
    state.mark_sent("group_1", NOW)
    with pytest.raises(AutomaticRetryBlocked):
        state.reserve("group_1", "hash", NOW + timedelta(minutes=30))


def test_expired_sending_lease_becomes_uncertain():
    state = ReportState.empty("2026-07-05")
    state.reserve("group_1", "hash", NOW, lease_minutes=15)
    state.expire_leases(NOW + timedelta(minutes=16))
    assert state.groups["group_1"]["status"] == "uncertain"
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/test_state.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现状态机**

```python
from dataclasses import dataclass, field
from datetime import timedelta


class AutomaticRetryBlocked(RuntimeError):
    pass


@dataclass
class ReportState:
    business_date: str
    groups: dict = field(default_factory=dict)

    @classmethod
    def empty(cls, business_date):
        return cls(business_date)

    def reserve(self, group, content_hash, now, lease_minutes=15):
        current = self.groups.get(group, {})
        if current.get("status") in {"sent", "uncertain", "sending"}:
            raise AutomaticRetryBlocked(group)
        self.groups[group] = {
            "status": "sending",
            "content_hash": content_hash,
            "lease_expires_at": (now + timedelta(minutes=lease_minutes)).isoformat(),
        }

    def mark_sent(self, group, now):
        self.groups[group].update(status="sent", sent_at=now.isoformat())

    def mark_failed(self, group, error):
        self.groups[group].update(status="failed", error=str(error))

    def mark_uncertain(self, group, error):
        self.groups[group].update(status="uncertain", error=str(error))

    def expire_leases(self, now):
        for value in self.groups.values():
            if value.get("status") == "sending" and value["lease_expires_at"] < now.isoformat():
                value["status"] = "uncertain"
```

Initialize `report_state.json`:

```json
{"version":1,"days":{}}
```

- [ ] **Step 4: 运行测试并提交**

Run: `python -m pytest tests/test_state.py -v`

Expected: PASS。

```powershell
git add canyin_news/state.py tests/test_state.py report_state.json
git commit -m "feat: prevent automatic duplicate group sends"
```

### Task 8：实现字符预算渲染器

**Files:**
- Create: `canyin_news/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: 写失败测试**

```python
from canyin_news.render import render_report


def test_report_never_breaks_budget_or_markdown_links():
    sections = {"餐饮动态": [
        {"title": "很长的标题" * 10, "url": "https://example.com/a", "summary": "摘要" * 100,
         "source": "红餐网", "freshness_label": ""}
    ]}
    text = render_report("2026.07.05", sections, budget=500)
    assert len(text) <= 500
    assert text.count("[") == text.count("](")
    assert text.endswith("数据更新时间：2026.07.05")
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/test_render.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现完整条目预算**

```python
def _entry(item, summary_limit):
    summary = item.get("summary", "").strip()[:summary_limit]
    label = f' · {item["freshness_label"]}' if item.get("freshness_label") else ""
    body = f'**[{item["title"]}]({item["url"]})**{label}\n'
    if summary:
        body += f"{summary}\n"
    return body + f'来源：{item["source"]}\n\n'


def render_report(date_text, sections, budget=3600):
    header = f"## 📡 餐饮 AI 情报站 · {date_text}\n\n"
    footer = f"数据更新时间：{date_text}"
    output = header
    for name, items in sections.items():
        section = f"### {name}\n\n"
        if not items:
            section += "> 今日暂无符合标准的新资讯\n\n"
        for item in items:
            candidate = _entry(item, 90)
            if len(output) + len(section) + len(candidate) + len(footer) > budget:
                candidate = _entry(item, 40)
            if len(output) + len(section) + len(candidate) + len(footer) > budget:
                break
            section += candidate
        output += section
    result = output + footer
    if len(result) > budget:
        raise ValueError("fixed report structure exceeds markdown budget")
    return result
```

- [ ] **Step 4: 运行测试并提交**

Run: `python -m pytest tests/test_render.py -v`

Expected: PASS。

```powershell
git add canyin_news/render.py tests/test_render.py
git commit -m "feat: render complete markdown within budget"
```

## 里程碑二：多信源采集和日报流水线

### Task 9：实现统一来源接口和首批 AI RSS

**Files:**
- Create: `canyin_news/sources/base.py`
- Create: `canyin_news/sources/rss.py`
- Create: `config/sources.json`
- Test: `tests/test_sources.py`

- [ ] **Step 1: 写 RSS 失败测试**

```python
import responses
from canyin_news.sources.rss import fetch_rss


@responses.activate
def test_rss_missing_date_does_not_invent_now():
    responses.get("https://example.com/feed.xml", body="""<?xml version="1.0"?>
    <rss version="2.0"><channel><item><title>AI update</title>
    <link>https://example.com/a</link></item></channel></rss>""", status=200)
    result, health = fetch_rss("Example", "https://example.com/feed.xml")
    assert result[0].published_at is None
    assert health.valid_date_ratio == 0
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/test_sources.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现通用 RSS 适配器和健康结果**

`base.py`:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class SourceHealth:
    source: str
    ok: bool
    elapsed_ms: int
    article_count: int
    valid_date_ratio: float
    error: str = ""
```

`rss.py` 必须使用 `requests.get(timeout=(3, 10))`、`feedparser.loads()`、`parse_published_at()`，并在日期缺失时保留 `published_at=None`。

- [ ] **Step 4: 配置首批已验证 RSS**

```json
{
  "ai_rss": [
    {"name":"OpenAI","url":"https://openai.com/news/rss.xml"},
    {"name":"Google DeepMind","url":"https://deepmind.google/blog/rss.xml"},
    {"name":"Hugging Face","url":"https://huggingface.co/blog/feed.xml"},
    {"name":"NVIDIA","url":"https://blogs.nvidia.com/feed/"},
    {"name":"Microsoft Research","url":"https://www.microsoft.com/en-us/research/feed/"}
  ]
}
```

- [ ] **Step 5: 运行测试并提交**

Run: `python -m pytest tests/test_sources.py -v`

Expected: PASS。

```powershell
git add canyin_news/sources config/sources.json tests/test_sources.py
git commit -m "feat: add verified official AI feeds"
```

### Task 10：迁移现有来源并并行采集

**Files:**
- Create: `canyin_news/sources/legacy.py`
- Create: `canyin_news/sources/aihot.py`
- Modify: `scraper.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 写并行和硬截止失败测试**

```python
from datetime import datetime, timedelta, timezone
from canyin_news.pipeline import collect_sources


def test_slow_optional_source_does_not_block_deadline():
    def fast():
        return ["ok"], {"source": "fast", "ok": True}
    def slow():
        raise TimeoutError("deadline")
    articles, health = collect_sources(
        {"fast": fast, "slow": slow},
        deadline=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    assert articles == ["ok"]
    assert {x["source"] for x in health} == {"fast", "slow"}
```

- [ ] **Step 2: 运行并确认失败**

Run: `python -m pytest tests/test_pipeline.py::test_slow_optional_source_does_not_block_deadline -v`

Expected: FAIL。

- [ ] **Step 3: 将现有函数包装为统一来源**

从 `scraper.py` 移动红餐网、36氪、RSS 和 Exa 请求代码到 `legacy.py`；每个函数返回 `(list[Article], SourceHealth)`。删除所有缺失日期时调用 `now_iso()` 的逻辑。

- [ ] **Step 4: 实现并行收集**

使用 `concurrent.futures.ThreadPoolExecutor(max_workers=8)`。每个 future 在全局 deadline 前收集；超时来源记录失败健康状态，已完成来源继续参与后续流水线。

- [ ] **Step 5: 把 `scraper.py` 改为兼容入口**

```python
from canyin_news.pipeline import collect_and_write


if __name__ == "__main__":
    raise SystemExit(collect_and_write())
```

- [ ] **Step 6: 运行完整测试并提交**

Run: `python -m pytest -v`

Expected: all tests PASS。

```powershell
git add scraper.py canyin_news/sources canyin_news/pipeline.py tests
git commit -m "refactor: collect report sources through bounded adapters"
```

### Task 11：实现 prepare、send、watchdog 三阶段命令

**Files:**
- Modify: `canyin_news/pipeline.py`
- Create: `canyin_news/dingtalk.py`
- Modify: `scripts/dingtalk_report.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 写 DRY_RUN 和本地数据优先测试**

```python
def test_prepare_uses_local_articles_and_does_not_send(tmp_path, monkeypatch):
    local = tmp_path / "articles.json"
    local.write_text('{"articles":[]}', encoding="utf-8")
    calls = []
    monkeypatch.setattr("canyin_news.dingtalk.send", lambda *a, **k: calls.append(a))
    result = prepare_report(local, dry_run=True, output_dir=tmp_path)
    assert result.preview.exists()
    assert calls == []
```

- [ ] **Step 2: 实现命令契约**

```text
python -m canyin_news.pipeline prepare --dry-run
python -m canyin_news.pipeline prepare --production
python -m canyin_news.pipeline send --bundle report_bundle.json
python -m canyin_news.pipeline watchdog --business-date YYYY-MM-DD
```

`prepare` 完成采集、校验、选稿、渲染并写入 bundle；生产模式同时写入发送租约，但不调用钉钉。`send` 只读取 bundle 和已持久化租约，逐群发送并更新状态。`watchdog` 只读取状态并在未发送时返回非零状态。

- [ ] **Step 3: 实现钉钉结果分类**

```python
class DefiniteSendFailure(RuntimeError):
    pass


class UncertainSendResult(RuntimeError):
    pass
```

HTTP 成功且 `errcode == 0` 为成功；HTTP 明确返回业务错误为 definite failure；连接重置、读取超时或响应无法解析为 uncertain。

- [ ] **Step 4: 保留旧脚本兼容入口**

```python
from canyin_news.pipeline import main


if __name__ == "__main__":
    raise SystemExit(main(["prepare", "--production", "--send"]))
```

- [ ] **Step 5: 运行测试并提交**

Run: `python -m pytest -v`

Expected: all tests PASS，且测试不访问真实钉钉。

```powershell
git add canyin_news scripts/dingtalk_report.py tests
git commit -m "feat: add safe report prepare and send phases"
```

## 里程碑三：调度、部署和生产验证

### Task 12：合并 GitHub Actions 工作流

**Files:**
- Create: `.github/workflows/daily-report.yml`
- Modify: `.github/workflows/daily-update.yml`
- Modify: `.github/workflows/dingtalk-report.yml`

- [ ] **Step 1: 创建统一工作流**

工作流必须包含：

```yaml
name: 每日餐饮AI日报
on:
  workflow_dispatch:
    inputs:
      mode:
        type: choice
        options: [production, dry-run, watchdog]
        default: dry-run
  schedule:
    - cron: "47 1 * * *"
concurrency:
  group: daily-report-production
  cancel-in-progress: false
permissions:
  contents: write
```

生产 job 顺序固定为：

1. checkout。
2. Python 3.11 和依赖。
3. `prepare --production`。
4. 提交并推送 `articles.json`、`report_state.json`、`sent_history.json` 和 bundle 内容指纹。
5. `send`。
6. 再次提交发送结果状态。
7. 上传脱敏的预览和来源健康报告 artifact。

- [ ] **Step 2: 禁用旧生产触发**

将两个旧工作流改为仅支持手动 `workflow_dispatch`，并在 job 中输出迁移提示后退出。删除 `daily-update.yml` 的 `push` 和 `schedule`，删除 `dingtalk-report.yml` 的 `schedule`，避免重复生产任务。

- [ ] **Step 3: 加入状态提交冲突保护**

每次推送状态前执行：

```powershell
git pull --rebase origin main
git push origin HEAD:main
```

若 rebase 或 push 失败，发送步骤不得继续；状态持久化优先于外部发送。

- [ ] **Step 4: 用 actionlint 或 YAML 解析验证**

Run:

```powershell
python -c "import yaml, pathlib; [yaml.safe_load(p.read_text(encoding='utf-8')) for p in pathlib.Path('.github/workflows').glob('*.yml')]"
```

Expected: exit 0。

- [ ] **Step 5: 提交**

```powershell
git add .github/workflows
git commit -m "ci: unify daily report workflow"
```

### Task 13：实现 Cloudflare 免费触发器

**Files:**
- Create: `cloudflare-trigger/src/index.mjs`
- Create: `cloudflare-trigger/test/index.test.mjs`
- Create: `cloudflare-trigger/wrangler.jsonc`

- [ ] **Step 1: 写失败测试**

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import { dispatch } from "../src/index.mjs";

test("dispatch sends production input without exposing token", async () => {
  let request;
  const fakeFetch = async (url, options) => {
    request = { url, options };
    return new Response(null, { status: 204 });
  };
  await dispatch({ GITHUB_TOKEN: "secret", REPO: "owner/repo" }, "production", fakeFetch);
  assert.match(request.url, /daily-report.yml\/dispatches$/);
  assert.equal(JSON.parse(request.options.body).inputs.mode, "production");
  assert.doesNotMatch(request.options.body, /secret/);
});
```

- [ ] **Step 2: 运行并确认失败**

Run: `node --test cloudflare-trigger/test/index.test.mjs`

Expected: FAIL。

- [ ] **Step 3: 实现触发器**

```javascript
export async function dispatch(env, mode, fetchImpl = fetch) {
  const response = await fetchImpl(
    `https://api.github.com/repos/${env.REPO}/actions/workflows/daily-report.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "canyin-ai-news-scheduler",
      },
      body: JSON.stringify({ ref: "main", inputs: { mode } }),
    },
  );
  if (response.status !== 204) throw new Error(`GitHub dispatch failed: ${response.status}`);
}

export default {
  async scheduled(controller, env, ctx) {
    const mode = controller.cron === "20 1 * * *" ? "production" : "watchdog";
    ctx.waitUntil(dispatch(env, mode));
  },
};
```

`wrangler.jsonc`:

```json
{
  "name": "canyin-ai-news-scheduler",
  "main": "src/index.mjs",
  "compatibility_date": "2026-07-04",
  "triggers": {
    "crons": ["20 1 * * *", "5 2 * * *"]
  },
  "vars": {
    "REPO": "yuchuanwang001-source/canyin-ai-news"
  }
}
```

- [ ] **Step 4: 运行测试并提交**

Run: `node --test cloudflare-trigger/test/index.test.mjs`

Expected: PASS。

```powershell
git add cloudflare-trigger
git commit -m "feat: add free external report scheduler"
```

### Task 14：撤销泄露 Token 并配置最小权限凭据

**Files:**
- No repository file contains a secret.
- Verify: Desktop handoff document no longer contains the old token after user-approved edit.

- [ ] **Step 1: 在用户已登录的 GitHub 页面识别旧 PAT**

打开 GitHub Settings → Developer settings → Personal access tokens。根据创建时间和用途识别交接文档中的旧 classic PAT；不复制、不显示 Token 值。

- [ ] **Step 2: 撤销旧 PAT**

点击对应 Token 的 Delete/Revoke，确认撤销。随后验证 `gh auth status`；如果 CLI 使用的正是旧 Token，重新执行安全的设备登录。

- [ ] **Step 3: 创建细粒度 Token**

仅选择仓库 `yuchuanwang001-source/canyin-ai-news`，设置有效期，并只授予：

```text
Repository permissions → Actions: Read and write
Repository permissions → Metadata: Read-only（自动包含）
```

该 Token 只用于 Cloudflare 调用 workflow dispatch。

- [ ] **Step 4: 存入 Cloudflare Secret**

Run interactively:

```powershell
npx wrangler secret put GITHUB_TOKEN
```

Expected: 终端只提示 secret 已保存，不回显值。

- [ ] **Step 5: 删除交接文档中的明文 Token**

在用户确认后编辑桌面交接文档，将 Token 值替换为：

```text
GitHub Token：已撤销；新凭据仅保存在 Cloudflare Secret，不写入文档。
```

- [ ] **Step 6: 安全验证**

Run:

```powershell
rg -n "ghp_|github_pat_|access_token=" . --hidden -g "!.git/**"
```

Expected: 生产代码和文档无 Token；测试中如有占位符必须是明显假值。

### Task 15：预览、测试群和生产验收

**Files:**
- Modify: `README.md`
- Generated artifact only: `report_preview.md`, source health JSON

- [ ] **Step 1: 运行完整自动测试**

Run:

```powershell
python -m pytest -v
node --test cloudflare-trigger/test/index.test.mjs
python -m py_compile scraper.py scripts/dingtalk_report.py canyin_news/*.py
```

Expected: all PASS，exit 0。

- [ ] **Step 2: 运行 DRY_RUN**

Run:

```powershell
$env:DRY_RUN="true"
python -m canyin_news.pipeline prepare --dry-run
```

Expected: 生成预览、来源健康和 bundle；没有钉钉网络请求。

- [ ] **Step 3: 审核预览**

确认：

```text
三个板块名称正确
每板块默认不超过 3 条
增量与补充标签正确
无重复文章
无未知日期伪装为今日
Markdown 在预算内
英文官方内容有中文说明
```

- [ ] **Step 4: 测试群发送**

配置独立 `DINGTALK_TEST_TOKEN`，运行：

```powershell
$env:TEST_GROUP="true"
python -m canyin_news.pipeline prepare --production --send
```

Expected: 只有测试群收到一份日报，正式群无消息。

- [ ] **Step 5: 重复发送演练**

立即再次执行相同命令。

Expected: 状态机阻止第二次发送，并输出 `already sent`。

- [ ] **Step 6: 生产启用**

在确认旧 Token 已撤销、测试群通过后，部署 Cloudflare Worker，手动 dispatch 一次 `dry-run`，最后启用生产模式。

- [ ] **Step 7: 连续三天观察**

每天记录：

```text
Cloudflare 触发时间
GitHub 开始时间
采集截止时间
发送完成时间
各来源健康
本期新增/近期补充数量
各群发送结果
```

验收：通常 10:00 前完成；无重复群发；AIHOT 故障不导致 AI 板块空白。

- [ ] **Step 8: 更新 README 并提交**

README 必须说明架构、三种运行模式、来源健康、Token 位置、手动恢复流程和“免费调度无严格 SLA”的边界。

```powershell
git add README.md
git commit -m "docs: document daily report operations"
```

## 最终验证

Run:

```powershell
git status --short
python -m pytest -v
node --test cloudflare-trigger/test/index.test.mjs
gh workflow view daily-report.yml
```

Expected:

```text
工作区干净
Python 和 Node 测试全部通过
统一工作流处于 active
旧定时工作流不再拥有 schedule 触发
仓库和交接文档中没有明文 Token
```
