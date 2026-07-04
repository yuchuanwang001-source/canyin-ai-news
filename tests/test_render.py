from canyin_news.render import render_report


def test_report_never_breaks_budget_or_markdown_links():
    sections = {
        "🍔 餐饮动态": [
            {
                "title": "很长的标题" * 10,
                "url": "https://example.com/a",
                "summary": "摘要" * 100,
                "source": "红餐网",
                "freshness_label": "",
            }
        ]
    }

    text = render_report("2026.07.05", "星期日", sections, budget=500)

    assert len(text) <= 500
    assert text.count("[") == text.count("](")
    assert text.endswith("数据更新时间：2026.07.05")


def test_entries_keep_familiar_numbered_layout():
    sections = {
        "🍔 餐饮动态": [
            {
                "title": "新品一",
                "url": "https://example.com/1",
                "summary": "摘要一",
                "source": "红餐网",
                "freshness_label": "",
            },
            {
                "title": "新品二",
                "url": "https://example.com/2",
                "summary": "摘要二",
                "source": "红餐网",
                "freshness_label": "补充阅读｜7月4日",
            },
        ]
    }

    text = render_report("2026.07.05", "星期日", sections)

    assert "**1️⃣ [新品一]" in text
    assert "**2️⃣ [新品二]" in text
    assert "补充阅读｜7月4日" in text
