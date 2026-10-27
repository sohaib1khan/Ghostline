"""Pure Python maze engine for Ghostwalk.

Learner code runs in the browser via Pyodide. The API only replays action lists
through the same rules — it never executes learner source.
"""

from __future__ import annotations

import ast
import re
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

KNOWN_COMMANDS = frozenset(
    {
        "move",
        "turn_left",
        "turn_right",
        "pick_up",
        "at_goal",
        "is_blocked",
        "on_gem",
        "read_sign",
        # Ghostfarm
        "plant",
        "water",
        "harvest",
        "on_soil",
        "crops_held",
    }
)
# ~ empty soil, s seeded, c crop ready; B barn treated like goal tile G
FARM_SOIL = "~"
FARM_SEED = "s"
FARM_CROP = "c"
FARM_BARN = "B"
FACINGS = ("N", "E", "S", "W")
DELTA = {"N": (-1, 0), "E": (0, 1), "S": (1, 0), "W": (0, -1)}
MAX_CODE_CHARS = 12_000
MAX_ACTIONS = 2_000
DEFAULT_MAX_STEPS = 500
# Instruction budget for run_learner_code (AST nodes / loop iterations).
INSTRUCTION_BUDGET = 50_000


@dataclass
class WorldState:
    grid: list[list[str]]
    row: int
    col: int
    facing: str
    gems_total: int
    gems_held: int = 0
    crops_total: int = 0
    crops_held: int = 0
    steps: int = 0
    max_steps: int = DEFAULT_MAX_STEPS
    goal: dict = field(default_factory=dict)
    allowed: set[str] = field(default_factory=set)
    actions: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    error: str | None = None
    error_line: int | None = None
    instructions: int = 0


def stars_for_lines(lines: int, par_lines: int) -> int:
    """3 at or under par, 2 within +2, else 1 on a successful clear."""
    par = max(1, int(par_lines or 1))
    used = max(0, int(lines))
    if used <= par:
        return 3
    if used <= par + 2:
        return 2
    return 1


def _normalize_grid(raw: list[str] | list[list[str]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in raw:
        if isinstance(line, str):
            rows.append(list(line))
        else:
            rows.append([str(cell) for cell in line])
    if not rows:
        raise ValueError("Grid is empty")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("Grid must be rectangular")
    return rows


def _find_char(grid: list[list[str]], needle: str) -> tuple[int, int] | None:
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell == needle:
                return r, c
    return None


def _count_gems(grid: list[list[str]]) -> int:
    return sum(cell == "*" for row in grid for cell in row)


def _count_soil(grid: list[list[str]]) -> int:
    return sum(cell == FARM_SOIL for row in grid for cell in row)


def _at_goal_cell(state: WorldState) -> bool:
    cell = _cell(state.grid, state.row, state.col)
    return cell in {"G", FARM_BARN}


def _cell(grid: list[list[str]], row: int, col: int) -> str:
    if row < 0 or col < 0 or row >= len(grid) or col >= len(grid[0]):
        return "#"
    return grid[row][col]


def _facing_name(facing: str) -> str:
    return {"N": "north", "E": "east", "S": "south", "W": "west"}.get(facing, facing)


def _snapshot(state: WorldState, *, line: int | None, message: str, kind: str) -> dict:
    return {
        "row": state.row,
        "col": state.col,
        "facing": state.facing,
        "gems_held": state.gems_held,
        "gems_total": state.gems_total,
        "crops_held": state.crops_held,
        "crops_total": state.crops_total,
        "steps": state.steps,
        "line": line,
        "message": message,
        "kind": kind,
        "grid": ["".join(row) for row in state.grid],
    }


def _fail(state: WorldState, message: str, line: int | None = None) -> None:
    state.error = message
    state.error_line = line
    state.trace.append(_snapshot(state, line=line, message=message, kind="error"))


def _tick(state: WorldState) -> bool:
    state.instructions += 1
    if state.instructions > INSTRUCTION_BUDGET:
        _fail(state, "That ran too long. Check for an infinite loop.")
        return False
    return state.error is None


def build_state(level: dict) -> WorldState:
    grid = _normalize_grid(level.get("grid") or [])
    start = level.get("start") or {}
    facing = str(start.get("facing") or level.get("facing") or "E").upper()
    if facing not in FACINGS:
        facing = "E"
    s_pos = _find_char(grid, "S")
    row = int(start.get("row", s_pos[0] if s_pos else 0))
    col = int(start.get("col", s_pos[1] if s_pos else 0))
    # Treat S as floor once placed.
    if _cell(grid, row, col) == "S":
        grid[row][col] = "."
    g_pos = _find_char(grid, "G")
    if g_pos and _cell(grid, g_pos[0], g_pos[1]) == "G":
        # Keep G on the map for at_goal checks.
        pass
    allowed = {str(item) for item in (level.get("allowed") or []) if str(item) in KNOWN_COMMANDS}
    if not allowed:
        allowed = set(KNOWN_COMMANDS)
    goal = dict(level.get("goal") or {"reach_goal": True})
    crops_needed = int(goal.get("collect_crops") or 0)
    return WorldState(
        grid=grid,
        row=row,
        col=col,
        facing=facing,
        gems_total=_count_gems(grid),
        crops_total=crops_needed or _count_soil(grid),
        max_steps=int(level.get("max_steps") or DEFAULT_MAX_STEPS),
        goal=goal,
        allowed=allowed,
    )


def _require(state: WorldState, command: str, line: int | None) -> bool:
    if command not in state.allowed:
        _fail(state, f"`hero.{command}()` is not unlocked on this level.", line)
        return False
    return True


def _ahead(state: WorldState) -> tuple[int, int]:
    dr, dc = DELTA[state.facing]
    return state.row + dr, state.col + dc


def do_move(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "move", line):
        return False
    if state.steps >= state.max_steps:
        _fail(state, "Too many steps. Simplify the path.", line)
        return False
    nr, nc = _ahead(state)
    if _cell(state.grid, nr, nc) == "#":
        _fail(state, "Bonk — a wall is ahead. Check with hero.is_blocked().", line)
        return False
    state.row, state.col = nr, nc
    state.steps += 1
    state.actions.append({"op": "move", "line": line})
    msg = f"Moved {_facing_name(state.facing)} to row {state.row}, column {state.col}"
    state.trace.append(_snapshot(state, line=line, message=msg, kind="move"))
    return True


def do_turn(state: WorldState, direction: str, line: int | None = None) -> bool:
    cmd = "turn_left" if direction == "left" else "turn_right"
    if not _tick(state) or not _require(state, cmd, line):
        return False
    idx = FACINGS.index(state.facing)
    state.facing = FACINGS[(idx - 1) % 4] if direction == "left" else FACINGS[(idx + 1) % 4]
    state.actions.append({"op": cmd, "line": line})
    msg = f"Turned {direction}, now facing {_facing_name(state.facing)}"
    state.trace.append(_snapshot(state, line=line, message=msg, kind="turn"))
    return True


def do_pick_up(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "pick_up", line):
        return False
    if _cell(state.grid, state.row, state.col) != "*":
        _fail(state, "Nothing to pick up here. Check hero.on_gem() first.", line)
        return False
    state.grid[state.row][state.col] = "."
    state.gems_held += 1
    state.actions.append({"op": "pick_up", "line": line})
    msg = f"Picked up a gem ({state.gems_held}/{state.gems_total})"
    state.trace.append(_snapshot(state, line=line, message=msg, kind="pick_up"))
    return True


def query_at_goal(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "at_goal", line):
        return False
    return _at_goal_cell(state)


def do_plant(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "plant", line):
        return False
    if _cell(state.grid, state.row, state.col) != FARM_SOIL:
        _fail(state, "Plant only works on empty soil (~).", line)
        return False
    state.grid[state.row][state.col] = FARM_SEED
    state.actions.append({"op": "plant", "line": line})
    state.trace.append(
        _snapshot(state, line=line, message="Planted a seed.", kind="plant")
    )
    return True


def do_water(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "water", line):
        return False
    if _cell(state.grid, state.row, state.col) != FARM_SEED:
        _fail(state, "Water only works on a planted seed.", line)
        return False
    state.grid[state.row][state.col] = FARM_CROP
    state.actions.append({"op": "water", "line": line})
    state.trace.append(
        _snapshot(state, line=line, message="Watered the seed — crop ready!", kind="water")
    )
    return True


def do_harvest(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "harvest", line):
        return False
    if _cell(state.grid, state.row, state.col) != FARM_CROP:
        _fail(state, "Nothing ripe to harvest here.", line)
        return False
    state.grid[state.row][state.col] = FARM_SOIL
    state.crops_held += 1
    state.actions.append({"op": "harvest", "line": line})
    msg = f"Harvested a crop ({state.crops_held}/{state.crops_total})"
    state.trace.append(_snapshot(state, line=line, message=msg, kind="harvest"))
    return True


def query_on_soil(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "on_soil", line):
        return False
    return _cell(state.grid, state.row, state.col) in {FARM_SOIL, FARM_SEED, FARM_CROP}


def query_crops_held(state: WorldState, line: int | None = None) -> int:
    if not _tick(state) or not _require(state, "crops_held", line):
        return 0
    return state.crops_held


def query_is_blocked(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "is_blocked", line):
        return False
    nr, nc = _ahead(state)
    return _cell(state.grid, nr, nc) == "#"


def query_on_gem(state: WorldState, line: int | None = None) -> bool:
    if not _tick(state) or not _require(state, "on_gem", line):
        return False
    return _cell(state.grid, state.row, state.col) == "*"


def query_read_sign(state: WorldState, line: int | None = None) -> str | None:
    if not _tick(state) or not _require(state, "read_sign", line):
        return None
    cell = _cell(state.grid, state.row, state.col)
    if cell == "r":
        return "red"
    if cell == "b":
        return "blue"
    return None


def goals_met(state: WorldState) -> bool:
    goal = state.goal or {}
    if goal.get("collect_all_gems") and state.gems_held < state.gems_total:
        return False
    need_crops = int(goal.get("collect_crops") or 0)
    if need_crops and state.crops_held < need_crops:
        return False
    if goal.get("reach_goal", True) and not _at_goal_cell(state):
        return False
    return True


def _result(state: WorldState, *, ok: bool | None = None) -> dict[str, Any]:
    success = ok if ok is not None else (state.error is None and goals_met(state))
    out: dict[str, Any] = {
        "ok": success,
        "error": state.error,
        "error_line": state.error_line,
        "trace": state.trace,
        "actions": state.actions,
        "steps": state.steps,
        "gems_held": state.gems_held,
        "gems_total": state.gems_total,
        "crops_held": state.crops_held,
        "crops_total": state.crops_total,
        "row": state.row,
        "col": state.col,
        "facing": state.facing,
    }
    if not success and state.error is None:
        need_crops = int(state.goal.get("collect_crops") or 0)
        if state.goal.get("collect_all_gems") and state.gems_held < state.gems_total:
            out["error"] = (
                f"Still missing gems ({state.gems_held}/{state.gems_total})."
            )
        elif need_crops and state.crops_held < need_crops:
            out["error"] = (
                f"Still missing crops ({state.crops_held}/{need_crops})."
            )
        else:
            out["error"] = "The ghost did not reach the goal."
    return out


def replay(level: dict, actions: list[dict] | list[str]) -> dict[str, Any]:
    """Server-side validation of a submitted move list."""
    if not isinstance(actions, list):
        return {
            "ok": False,
            "error": "Actions must be a list.",
            "error_line": None,
            "trace": [],
            "actions": [],
        }
    if len(actions) > MAX_ACTIONS:
        return {
            "ok": False,
            "error": "Too many actions.",
            "error_line": None,
            "trace": [],
            "actions": [],
        }
    try:
        state = build_state(deepcopy(level))
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "error_line": None,
            "trace": [],
            "actions": [],
        }
    state.trace.append(
        _snapshot(state, line=None, message="Ready.", kind="start")
    )
    for raw in actions:
        if state.error:
            break
        if isinstance(raw, str):
            op = raw
            line = None
        elif isinstance(raw, dict):
            op = str(raw.get("op") or raw.get("action") or "")
            line = raw.get("line")
            if line is not None:
                try:
                    line = int(line)
                except (TypeError, ValueError):
                    line = None
        else:
            _fail(state, "Invalid action entry.")
            break
        if op == "move":
            do_move(state, line)
        elif op == "turn_left":
            do_turn(state, "left", line)
        elif op == "turn_right":
            do_turn(state, "right", line)
        elif op == "pick_up":
            do_pick_up(state, line)
        elif op == "plant":
            do_plant(state, line)
        elif op == "water":
            do_water(state, line)
        elif op == "harvest":
            do_harvest(state, line)
        elif op in {
            "at_goal",
            "is_blocked",
            "on_gem",
            "read_sign",
            "on_soil",
            "crops_held",
        }:
            # Queries should not appear in submit action lists; ignore soft.
            continue
        else:
            _fail(state, f"Unknown action `{op}`.", line)
            break
    return _result(state)


class _Hero:
    def __init__(self, state: WorldState, line_tracker: dict) -> None:
        self._state = state
        self._line = line_tracker

    def _ln(self) -> int | None:
        return self._line.get("current")

    def move(self) -> None:
        do_move(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)

    def turn_left(self) -> None:
        do_turn(self._state, "left", self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)

    def turn_right(self) -> None:
        do_turn(self._state, "right", self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)

    def pick_up(self) -> None:
        do_pick_up(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)

    def at_goal(self) -> bool:
        value = query_at_goal(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)
        return value

    def is_blocked(self) -> bool:
        value = query_is_blocked(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)
        return value

    def on_gem(self) -> bool:
        value = query_on_gem(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)
        return value

    def read_sign(self) -> str | None:
        value = query_read_sign(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)
        return value

    def plant(self) -> None:
        do_plant(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)

    def water(self) -> None:
        do_water(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)

    def harvest(self) -> None:
        do_harvest(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)

    def on_soil(self) -> bool:
        value = query_on_soil(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)
        return value

    def crops_held(self) -> int:
        value = query_crops_held(self._state, self._ln())
        if self._state.error:
            raise RuntimeError(self._state.error)
        return value


def _instrument_lines(tree: ast.AST, tracker_name: str) -> ast.AST:
    """Inject line tracker updates before each statement for error_line reporting."""

    class Transformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            self.generic_visit(node)
            return node

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
            self.generic_visit(node)
            return node

        def _mark(self, node: ast.stmt) -> list[ast.stmt]:
            assign = ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id=tracker_name, ctx=ast.Load()),
                        slice=ast.Constant(value="current"),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Constant(value=getattr(node, "lineno", None)),
            )
            ast.copy_location(assign, node)
            return [assign, node]

        def visit_Module(self, node: ast.Module) -> ast.Module:
            body: list[ast.stmt] = []
            for stmt in node.body:
                stmt = self.visit(stmt)
                if isinstance(stmt, ast.stmt):
                    body.extend(self._mark(stmt))
                elif isinstance(stmt, list):
                    body.extend(stmt)
            node.body = body
            return node

    return Transformer().visit(tree)


def run_learner_code(level: dict, code: str) -> dict[str, Any]:
    """Execute learner Python against a level (browser / unit tests)."""
    if not isinstance(code, str):
        return {
            "ok": False,
            "error": "Code must be a string.",
            "error_line": None,
            "trace": [],
            "actions": [],
        }
    if len(code) > MAX_CODE_CHARS:
        return {
            "ok": False,
            "error": "That program is too long.",
            "error_line": None,
            "trace": [],
            "actions": [],
        }
    # Soft block of dangerous builtins names in source (defense in depth; exec is locked down).
    if re.search(r"\b(__import__|open|exec|eval|compile|input)\b", code):
        return {
            "ok": False,
            "error": "That code uses a blocked built-in.",
            "error_line": None,
            "trace": [],
            "actions": [],
        }
    try:
        state = build_state(deepcopy(level))
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "error_line": None,
            "trace": [],
            "actions": [],
        }
    state.trace.append(_snapshot(state, line=None, message="Ready.", kind="start"))
    line_tracker: dict[str, int | None] = {"current": None}
    hero = _Hero(state, line_tracker)
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return {
            "ok": False,
            "error": f"Syntax error: {exc.msg}",
            "error_line": exc.lineno,
            "trace": state.trace,
            "actions": [],
        }
    tree = _instrument_lines(tree, "_gw_line")
    ast.fix_missing_locations(tree)
    compiled = compile(tree, "<ghostwalk>", "exec")
    env = {
        "hero": hero,
        "_gw_line": line_tracker,
        "__builtins__": {
            "range": range,
            "len": len,
            "int": int,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "enumerate": enumerate,
            "min": min,
            "max": max,
            "sum": sum,
            "abs": abs,
            "True": True,
            "False": False,
            "None": None,
            "print": lambda *args, **kwargs: None,
        },
    }

    def _tracer(_frame, event, _arg):  # noqa: ANN001
        if event != "line":
            return _tracer
        state.instructions += 1
        if state.instructions > INSTRUCTION_BUDGET:
            _fail(state, "That ran too long. Check for an infinite loop.")
            raise RuntimeError(state.error)
        return _tracer

    previous = sys.gettrace()
    try:
        sys.settrace(_tracer)
        exec(compiled, env, env)  # noqa: S102 — intentional sandboxed learner exec
    except RuntimeError:
        return _result(state, ok=False)
    except Exception as exc:  # noqa: BLE001 — surface learner errors
        line = line_tracker.get("current")
        if state.error is None:
            _fail(state, str(exc) or "Runtime error.", line)
        return _result(state, ok=False)
    finally:
        sys.settrace(previous)
    return _result(state)
