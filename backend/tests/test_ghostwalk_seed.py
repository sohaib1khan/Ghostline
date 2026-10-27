"""Every seeded Ghostwalk solution must clear via skins (or world for Python)."""

from pathlib import Path

import pytest
import yaml

from app.ghostwalk import skins, world
from app.services.ghostwalk import parse_import_document, validate_level_payload

SEED_DIR = Path(__file__).resolve().parents[1] / "app" / "seed" / "ghostwalk"


def _seed_levels() -> list[dict]:
    rows: list[dict] = []
    for name in ("levels.yaml", "levels_multilang.yaml"):
        path = SEED_DIR / name
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rows.extend(loaded.get("levels") or [])
    return rows


@pytest.mark.parametrize(
    "item",
    [pytest.param(row, id=str(row.get("slug"))) for row in _seed_levels()],
)
def test_seeded_solution_clears(item: dict) -> None:
    errors = validate_level_payload(item)
    assert errors == [], errors
    lang = (item.get("language") or "python").lower()
    if lang == "javascript":
        pytest.skip("JavaScript solutions are checked via world.js in Node/e2e")
    level = {
        key: item[key]
        for key in ("grid", "start", "allowed", "goal", "max_steps")
        if key in item
    }
    ran = skins.run(world, level, lang, item.get("solution") or "")
    assert ran.get("ok") is True, f"{item.get('slug')}: {ran.get('error')} @ {ran.get('error_line')}"
    checked = world.replay(level, ran.get("actions") or [])
    assert checked.get("ok") is True, f"{item.get('slug')} replay: {checked.get('error')}"


def test_export_fields_keep_language_on_reimport() -> None:
    """Re-importing an export must preserve each level's language."""
    sample = {
        "levels": [
            {
                "slug": "bash-sample",
                "order": 1,
                "title": "Bash sample",
                "concept": "move",
                "intro_markdown": "",
                "grid": ["###", "#SG", "###"],
                "start": {"row": 1, "col": 1, "facing": "E"},
                "allowed": ["move"],
                "goal": {"reach_goal": True},
                "max_steps": 50,
                "mode": "free",
                "language": "bash",
                "starter_code": "move\n",
                "solution": "move\n",
                "hints": [],
                "par_lines": 1,
                "xp": 10,
                "status": "published",
            },
            {
                "slug": "go-sample",
                "order": 1,
                "title": "Go sample",
                "concept": "move",
                "intro_markdown": "",
                "grid": ["###", "#SG", "###"],
                "start": {"row": 1, "col": 1, "facing": "E"},
                "allowed": ["move"],
                "goal": {"reach_goal": True},
                "max_steps": 50,
                "mode": "free",
                "language": "go",
                "starter_code": "hero.Move()\n",
                "solution": "hero.Move()\n",
                "hints": [],
                "par_lines": 1,
                "xp": 10,
                "status": "published",
            },
        ]
    }
    dumped = yaml.safe_dump(sample, sort_keys=False)
    # Simulate export including language (the router field list).
    assert "language: bash" in dumped
    assert "language: go" in dumped
    rows = parse_import_document(dumped)
    assert [row.get("language") for row in rows] == ["bash", "go"]
    for row in rows:
        assert validate_level_payload(row) == []
