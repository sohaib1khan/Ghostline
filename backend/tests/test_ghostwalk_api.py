"""Ghostwalk API rules — lock order, solution hiding, replay, stars, limits."""

from app.ghostwalk.world import replay, run_learner_code, stars_for_lines
from app.services.ghostwalk import (
    MAX_ACTIONS,
    MAX_CODE_CHARS,
    count_code_lines,
    validate_level_payload,
)

FIRST = {
    "grid": ["#######", "#S...G#", "#######"],
    "start": {"row": 1, "col": 1, "facing": "E"},
    "allowed": ["move"],
    "goal": {"reach_goal": True},
    "max_steps": 500,
    "par_lines": 4,
}


def test_validate_level_rejects_bad_grid() -> None:
    errors = validate_level_payload(
        {
            "grid": ["##", "#"],
            "start": {"row": 0, "col": 0},
            "allowed": ["move"],
            "par_lines": 1,
            "mode": "free",
        }
    )
    assert errors


def test_validate_level_ok() -> None:
    errors = validate_level_payload(
        {
            "grid": ["###", "#SG", "###"],
            "start": {"row": 1, "col": 1},
            "allowed": ["move"],
            "par_lines": 2,
            "mode": "guided",
        }
    )
    assert errors == []


def test_solution_actions_replay_clean() -> None:
    code = "hero.move()\n" * 4
    ran = run_learner_code(FIRST, code)
    assert ran["ok"]
    checked = replay(FIRST, ran["actions"])
    assert checked["ok"] is True


def test_forged_wall_rejected() -> None:
    level = {**FIRST, "allowed": ["move", "turn_left"]}
    result = replay(level, [{"op": "turn_left"}, {"op": "move"}])
    assert result["ok"] is False


def test_stars_and_line_count() -> None:
    assert stars_for_lines(4, 4) == 3
    assert count_code_lines("hero.move()\n\n# hi\nhero.move()\n") == 2


def test_oversized_limits() -> None:
    assert MAX_ACTIONS == 2000
    assert MAX_CODE_CHARS == 12_000
