import json
from pathlib import Path

import pytest

from canyin_news.classify import classify_article


CASES = json.loads(
    Path("tests/fixtures/classification_cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES)
def test_classification_cases(case):
    assert (
        classify_article(case["title"], case["summary"], case["source"])
        == case["expected"]
    )
