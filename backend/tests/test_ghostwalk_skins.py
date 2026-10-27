"""Tests for Ghostwalk language skins. Copy to backend/tests/test_ghostwalk_skins.py."""

import pytest
from app.ghostwalk import skins, world

CORRIDOR = {
    "grid": ["#######", "#S...G#", "#######"],
    "start": {"row": 1, "col": 1, "facing": "E"},
    "allowed": [
        "move",
        "turn_left",
        "turn_right",
        "at_goal",
        "is_blocked",
        "read_sign",
        "on_gem",
        "pick_up",
    ],
    "goal": {"reach_goal": True},
    "max_steps": 500,
}


def run(lang, code):
    return skins.run(world, CORRIDOR, lang, code)


@pytest.mark.parametrize(
    ("lang", "code"),
    [
        ("bash", "move; move; move; move\n"),
        ("bash", "for i in {1..4}; do move; done\n"),
        ("bash", "for i in $(seq 4); do\n  move\ndone\n"),
        (
            "bash",
            "until at_goal; do\n  if blocked; then\n    turn_left\n  elif on_gem; then\n"
            "    pick_up\n  else\n    move\n  fi\ndone\n",
        ),
        ("bash", "n=4\nfor ((i = 0; i < n; i++)); do move; done\n"),
        ("bash", "step() { move; }\nstep; step; step; step\n"),
        (
            "bash",
            "hero_move()\nhero_move()\nhero_move()\nhero_move()\n",
        ),  # older syntax still accepted
        ("go", "for range 4 {\n\thero.Move()\n}\n"),
        (
            "go",
            "for !hero.AtGoal() {\n\tswitch {\n\tcase hero.IsBlocked():\n\t\thero.TurnLeft()\n"
            "\tdefault:\n\t\thero.Move()\n\t}\n}\n",
        ),
        (
            "go",
            "steps := []int{2, 2}\nfor _, n := range steps {\n\tfor i := 0; i < n; i++ {\n"
            "\t\thero.Move()\n\t}\n}\n",
        ),
        ("csharp", "for (int i = 0; i < 4; i++) hero.Move();\n"),
        (
            "csharp",
            "while (!hero.AtGoal())\n{\n    if (hero.IsBlocked())\n        hero.TurnLeft();\n"
            "    else if (hero.OnGem())\n        hero.PickUp();\n    else\n"
            "        hero.Move();\n}\n",
        ),
        ("java", "for (int i = 1; i <= 4; i++) {\n    hero.move();\n}\n"),
        (
            "java",
            'while (!hero.atGoal()) {\n    String s = hero.readSign();\n    switch ("x") {\n'
            '        case "red" -> hero.turnLeft();\n        default -> hero.move();\n    }\n'
            "}\n",
        ),
        (
            "sql",
            "DO $$\nBEGIN\n  WHILE NOT at_goal() LOOP\n    IF is_blocked() THEN\n"
            "      CALL turn_left();\n    ELSIF on_gem() THEN\n      CALL pick_up();\n"
            "    ELSE\n      CALL move();\n    END IF;\n  END LOOP;\nEND $$;\n",
        ),
    ],
)
def test_valid_programs_solve(lang, code):
    result = run(lang, code)
    assert result["ok"], result["error"]


@pytest.mark.parametrize(
    ("lang", "code", "line", "fragment"),
    [
        ("bash", "move\nmvoe\n", 2, "command not found"),
        ("bash", "for i in {1..3}; do\n  move\n", 1, "never closed"),
        ("bash", "if blocked; then\n  move\ndone\n", 3, "closes"),
        ("go", "hero.move()\n", 1, "PascalCase"),
        ("go", "func hop() {\n}\n", 1, "closure"),
        ("go", "for !hero.AtGoal()\n{\n\thero.Move()\n}\n", 1, "same line"),
        (
            "csharp",
            'switch (hero.ReadSign())\n{\n    case "red":\n        hero.TurnLeft();\n}\n',
            3,
            "break",
        ),
        ("java", "hero.Move();\n", 1, "camelCase"),
        ("java", "Runnable r = () -> {\n    hero.move();\n};\nr();\n", 4, ".run()"),
        ("sql", "move();\n", 1, "CALL"),
        ("sql", "DO $$\nBEGIN\n  FOREACH n IN ARRAY x LOOP\n  END LOOP;\nEND $$;\n", 3, "DECLARE"),
    ],
)
def test_friendly_errors_point_at_the_right_line(lang, code, line, fragment):
    result = run(lang, code)
    assert not result["ok"]
    assert result["error_line"] == line
    assert fragment.lower() in result["error"].lower()


@pytest.mark.parametrize(
    ("lang", "code"),
    [
        ("go", 'x := __import__("os")\n'),
        ("go", "x := hero.__class__\n"),
        ("csharp", 'var x = System.IO.File.ReadAllText("/etc/passwd");\n'),
        ("java", "System.exit(0);\n"),
        ("java", "var x = hero.getClass();\n"),
        ("bash", "rm -rf /\n"),
        ("bash", "x=$(cat /etc/passwd)\n"),
        ("sql", "DO $$\nDECLARE\n  x int := __import__('os');\nBEGIN\nEND $$;\n"),
        ("sql", "DROP TABLE users;\n"),
    ],
)
def test_anything_outside_the_subset_is_rejected(lang, code):
    with pytest.raises(skins.SkinError):
        skins.transpile(lang, code)


def test_line_map_points_trace_at_learner_lines():
    code = "until at_goal; do\n  move\ndone\n"
    result = run("bash", code)
    assert result["ok"]
    assert {step["line"] for step in result["trace"] if step["line"]} == {2}


def test_java_switch_on_null_throws_like_java():
    code = "switch (hero.readSign()) {\n    default -> hero.move();\n}\n"
    result = run("java", code)
    assert not result["ok"]
    assert "NullPointerException" in result["error"]
