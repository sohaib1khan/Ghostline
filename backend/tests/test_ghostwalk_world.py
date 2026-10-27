"""Ghostwalk world engine — solutions, bumps, gems, forged moves."""

from app.ghostwalk.world import replay, run_learner_code, stars_for_lines

FIRST_STEPS = {
    "grid": ["#######", "#S...G#", "#######"],
    "start": {"row": 1, "col": 1, "facing": "E"},
    "allowed": ["move"],
    "goal": {"reach_goal": True},
    "max_steps": 500,
}


def test_stars_for_lines() -> None:
    assert stars_for_lines(4, 4) == 3
    assert stars_for_lines(5, 4) == 2
    assert stars_for_lines(6, 4) == 2
    assert stars_for_lines(7, 4) == 1


def test_first_steps_solution() -> None:
    code = "hero.move()\nhero.move()\nhero.move()\nhero.move()\n"
    result = run_learner_code(FIRST_STEPS, code)
    assert result["ok"] is True
    assert len(result["actions"]) == 4
    assert all(item["op"] == "move" for item in result["actions"])


def test_wall_bump_fails() -> None:
    code = "hero.move()\n" * 10
    result = run_learner_code(FIRST_STEPS, code)
    assert result["ok"] is False
    assert result["error"]
    assert "wall" in result["error"].lower() or "Bonk" in (result["error"] or "")


def test_forged_wall_walk_rejected_by_replay() -> None:
    # Walk through the north wall from start.
    forged = [{"op": "turn_left"}, {"op": "move"}]
    # turn_left not allowed on first-steps
    result = replay(FIRST_STEPS, forged)
    assert result["ok"] is False


def test_forged_extra_moves_through_goal_wall() -> None:
    # After four moves at goal, another move hits wall.
    actions = [{"op": "move"} for _ in range(5)]
    result = replay(FIRST_STEPS, actions)
    assert result["ok"] is False


def test_gem_collection() -> None:
    level = {
        "grid": ["#####", "#S*G#", "#####"],
        "start": {"row": 1, "col": 1, "facing": "E"},
        "allowed": ["move", "pick_up"],
        "goal": {"collect_all_gems": True, "reach_goal": True},
        "max_steps": 50,
    }
    code = "hero.move()\nhero.pick_up()\nhero.move()\n"
    result = run_learner_code(level, code)
    assert result["ok"] is True
    assert result["gems_held"] == 1


def test_oversized_code_rejected() -> None:
    result = run_learner_code(FIRST_STEPS, "x" * 20_000)
    assert result["ok"] is False
    assert "too long" in (result["error"] or "").lower()


def test_infinite_loop_budget() -> None:
    result = run_learner_code(
        FIRST_STEPS,
        "while True:\n    pass\n",
    )
    assert result["ok"] is False
    assert "too long" in (result["error"] or "").lower()


def test_nested_loop_error_line_points_at_body() -> None:
    """Moves inside a while must report the body line, not the while header."""
    # Dead-end corridor: move-only cannot reach G; the third move hits a wall.
    level = {
        "grid": ["######", "#S..##", "##G###", "######"],
        "start": {"row": 1, "col": 1, "facing": "E"},
        "allowed": ["move", "at_goal"],
        "goal": {"reach_goal": True},
        "max_steps": 500,
    }
    # Line 1: while …  Line 2: hero.move()
    code = "while not hero.at_goal():\n    hero.move()\n"
    result = run_learner_code(level, code)
    assert result["ok"] is False
    assert result["error_line"] == 2
    move_lines = [
        frame.get("line")
        for frame in (result.get("trace") or [])
        if frame.get("kind") == "move"
    ]
    assert move_lines
    assert all(line == 2 for line in move_lines)
