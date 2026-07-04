from canyin_news.annotations import chinese_note_for_english_title


def test_deepmind_partnership_gets_specific_chinese_note():
    note = chinese_note_for_english_title(
        "Google DeepMind and A24 announce first-of-its-kind research partnership",
        "Google DeepMind",
    )

    assert "Google DeepMind 与 A24 宣布" in note
    assert "研究合作" in note


def test_chinese_title_needs_no_extra_note():
    assert chinese_note_for_english_title("OpenAI 发布新模型", "OpenAI") == ""
