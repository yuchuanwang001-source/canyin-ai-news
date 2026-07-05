import json
from pathlib import Path


def test_aihot_selected_api_is_the_first_ai_source():
    config = json.loads(
        Path("config/sources.json").read_text(encoding="utf-8")
    )

    assert config["aihot"]["mode"] == "selected"
    assert config["aihot"]["take"] == 50
