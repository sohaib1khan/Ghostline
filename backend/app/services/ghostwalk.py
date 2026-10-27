"""Ghostwalk levels, lock order, submit with server-side replay."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ghostwalk.world import KNOWN_COMMANDS, replay, stars_for_lines
from app.models.attempt_log import AttemptLog
from app.models.ghostwalk import GhostwalkLevel, GhostwalkProgress
from app.models.progress import UserStats
from app.models.user import User
from app.services.content_store import ContentError

MAX_ACTIONS = 2_000
MAX_CODE_CHARS = 12_000
WORLD_PATH = Path(__file__).resolve().parents[1] / "ghostwalk" / "world.py"
SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "ghostwalk" / "levels.yaml"


def level_dict(level: GhostwalkLevel) -> dict:
    return {
        "grid": level.grid,
        "start": level.start,
        "allowed": level.allowed,
        "goal": level.goal,
        "max_steps": level.max_steps,
    }


def count_code_lines(code: str) -> int:
    return sum(
        1
        for line in (code or "").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def validate_level_payload(data: dict) -> list[str]:
    errors: list[str] = []
    grid = data.get("grid") or []
    if not isinstance(grid, list) or not grid:
        errors.append("Grid is required.")
        return errors
    rows = [list(row) if not isinstance(row, list) else row for row in grid]
    if isinstance(grid[0], str):
        rows = [list(row) for row in grid]
    width = len(rows[0]) if rows else 0
    if width == 0 or any(len(row) != width for row in rows):
        errors.append("Grid must be rectangular.")
    flat = "".join("".join(row) if isinstance(row, list) else row for row in grid)
    if flat.count("S") != 1:
        errors.append("Grid needs exactly one S.")
    if flat.count("G") != 1:
        errors.append("Grid needs exactly one G.")
    start = data.get("start") or {}
    try:
        sr, sc = int(start.get("row")), int(start.get("col"))
        cell = rows[sr][sc] if 0 <= sr < len(rows) and 0 <= sc < width else None
        if cell not in {"S", "."}:
            # Require coords match S in the raw grid.
            on_s = (isinstance(grid[sr], str) and grid[sr][sc] == "S") or (
                isinstance(grid[sr], list) and grid[sr][sc] == "S"
            )
            if not on_s:
                errors.append("Start coordinates must point at S.")
    except (TypeError, ValueError, IndexError):
        errors.append("Start row/col are invalid.")
    allowed = data.get("allowed") or []
    for item in allowed:
        if str(item) not in KNOWN_COMMANDS:
            errors.append(f"Unknown command `{item}`.")
    if int(data.get("par_lines") or 0) < 1:
        errors.append("par_lines must be at least 1.")
    mode = data.get("mode") or "free"
    if mode not in {"guided", "free"}:
        errors.append("mode must be guided or free.")
    return errors


async def seed_ghostwalk_levels(session: AsyncSession) -> int:
    existing = await session.scalar(select(func.count()).select_from(GhostwalkLevel))
    if existing:
        return 0
    if not SEED_PATH.is_file():
        return 0
    loaded = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8")) or {}
    rows = loaded.get("levels") or []
    count = 0
    for item in rows:
        errors = validate_level_payload(item)
        if errors:
            continue
        session.add(
            GhostwalkLevel(
                slug=str(item["slug"]),
                position=int(item.get("order") or item.get("position") or 0),
                title=str(item.get("title") or item["slug"]),
                concept=str(item.get("concept") or ""),
                intro_markdown=str(item.get("intro_markdown") or ""),
                grid=item.get("grid") or [],
                start=item.get("start") or {},
                allowed=list(item.get("allowed") or []),
                goal=dict(item.get("goal") or {"reach_goal": True}),
                max_steps=int(item.get("max_steps") or 500),
                mode=str(item.get("mode") or "free"),
                starter_code=str(item.get("starter_code") or ""),
                solution=str(item.get("solution") or ""),
                hints=list(item.get("hints") or []),
                par_lines=int(item.get("par_lines") or 1),
                xp=int(item.get("xp") or 20),
                status=str(item.get("status") or "published"),
                python_lesson_slug=item.get("python_lesson_slug"),
            )
        )
        count += 1
    return count


def world_source() -> str:
    return WORLD_PATH.read_text(encoding="utf-8")


async def _published_levels(session: AsyncSession) -> list[GhostwalkLevel]:
    return list(
        (
            await session.scalars(
                select(GhostwalkLevel)
                .where(GhostwalkLevel.status == "published")
                .order_by(GhostwalkLevel.position, GhostwalkLevel.slug)
            )
        ).all()
    )


async def _progress_map(
    session: AsyncSession, user_id: uuid.UUID, level_ids: list[uuid.UUID]
) -> dict[uuid.UUID, GhostwalkProgress]:
    if not level_ids:
        return {}
    rows = list(
        (
            await session.scalars(
                select(GhostwalkProgress).where(
                    GhostwalkProgress.user_id == user_id,
                    GhostwalkProgress.level_id.in_(level_ids),
                )
            )
        ).all()
    )
    return {row.level_id: row for row in rows}


async def list_levels_for_user(session: AsyncSession, user: User) -> dict:
    levels = await _published_levels(session)
    progress = await _progress_map(session, user.id, [level.id for level in levels])
    cards = []
    prev_complete = True
    solved = 0
    stars_total = 0
    stars_earned = 0
    for level in levels:
        row = progress.get(level.id)
        unlocked = prev_complete
        completed = bool(row and row.status == "completed")
        if completed:
            solved += 1
            stars_earned += int(row.stars or 0)
        stars_total += 3
        cards.append(
            {
                "id": level.id,
                "slug": level.slug,
                "order": level.position,
                "title": level.title,
                "concept": level.concept,
                "mode": level.mode,
                "par_lines": level.par_lines,
                "xp": level.xp,
                "unlocked": unlocked,
                "lock_reason": None
                if unlocked
                else (
                    f"Solve {levels[levels.index(level) - 1].title} first"
                    if levels.index(level) > 0
                    else "Locked"
                ),
                "stars": int(row.stars or 0) if row else 0,
                "completed": completed,
                "python_lesson_slug": level.python_lesson_slug,
            }
        )
        prev_complete = completed
    continue_at = None
    for card in cards:
        if card["unlocked"] and not card["completed"]:
            continue_at = {"slug": card["slug"], "title": card["title"], "order": card["order"]}
            break
    return {
        "levels": cards,
        "solved": solved,
        "total": len(cards),
        "stars_earned": stars_earned,
        "stars_total": stars_total,
        "continue": continue_at,
    }


async def get_level_for_user(
    session: AsyncSession, user: User, slug: str, *, memory_mode: bool = False
) -> dict:
    levels = await _published_levels(session)
    level = next((item for item in levels if item.slug == slug), None)
    if level is None:
        raise ContentError(404, "Level not found")
    progress = await _progress_map(session, user.id, [item.id for item in levels])
    # Lock check
    for item in levels:
        if item.slug == slug:
            break
        row = progress.get(item.id)
        if not row or row.status != "completed":
            raise ContentError(403, f"Solve {item.title} first")
    row = progress.get(level.id)
    show_solution = level.mode == "guided" and not memory_mode
    return {
        "id": level.id,
        "slug": level.slug,
        "order": level.position,
        "title": level.title,
        "concept": level.concept,
        "intro_markdown": level.intro_markdown,
        "grid": level.grid,
        "start": level.start,
        "allowed": level.allowed,
        "goal": level.goal,
        "max_steps": level.max_steps,
        "mode": "free" if memory_mode else level.mode,
        "starter_code": "" if memory_mode else level.starter_code,
        "solution": level.solution if show_solution else None,
        "hints": level.hints or [],
        "par_lines": level.par_lines,
        "xp": level.xp,
        "python_lesson_slug": level.python_lesson_slug,
        "progress": {
            "stars": int(row.stars or 0) if row else 0,
            "completed": bool(row and row.status == "completed"),
            "attempts": int(row.attempts or 0) if row else 0,
            "hints_used": int(row.hints_used or 0) if row else 0,
        },
    }


async def _ensure_progress(
    session: AsyncSession, user_id: uuid.UUID, level_id: uuid.UUID
) -> GhostwalkProgress:
    row = await session.scalar(
        select(GhostwalkProgress).where(
            GhostwalkProgress.user_id == user_id,
            GhostwalkProgress.level_id == level_id,
        )
    )
    if row is None:
        row = GhostwalkProgress(
            user_id=user_id,
            level_id=level_id,
            status="started",
            stars=0,
            attempts=0,
            hints_used=0,
            failed_runs=0,
        )
        session.add(row)
        await session.flush()
    return row


async def _stats_for(session: AsyncSession, user_id: uuid.UUID) -> UserStats:
    stats = await session.scalar(select(UserStats).where(UserStats.user_id == user_id))
    if stats is None:
        stats = UserStats(user_id=user_id, xp=0, current_streak_days=0, longest_streak_days=0)
        session.add(stats)
        await session.flush()
    return stats


async def submit_level(
    session: AsyncSession,
    user: User,
    slug: str,
    *,
    code: str,
    actions: list,
    hints_used: int = 0,
) -> dict:
    if not isinstance(code, str) or len(code) > MAX_CODE_CHARS:
        raise ContentError(400, "That program is too long.")
    if not isinstance(actions, list) or len(actions) > MAX_ACTIONS:
        raise ContentError(400, "Too many actions.")
    levels = await _published_levels(session)
    level = next((item for item in levels if item.slug == slug), None)
    if level is None:
        raise ContentError(404, "Level not found")
    # Enforce lock order
    progress_map = await _progress_map(session, user.id, [item.id for item in levels])
    for item in levels:
        if item.slug == slug:
            break
        prior = progress_map.get(item.id)
        if not prior or prior.status != "completed":
            raise ContentError(403, f"Solve {item.title} first")

    outcome = replay(level_dict(level), actions)
    row = await _ensure_progress(session, user.id, level.id)
    row.attempts = int(row.attempts or 0) + 1
    row.hints_used = max(int(row.hints_used or 0), int(hints_used or 0))

    # Mistake journal (Ghostwalk has no exercise_id).
    session.add(
        AttemptLog(
            user_id=user.id,
            exercise_id=None,
            submitted=(code or "")[:4000],
            passed=bool(outcome.get("ok")),
            failed_rule_hint=(outcome.get("error") or None)[:500] if outcome.get("error") else None,
            source="ghostwalk",
        )
    )

    if not outcome.get("ok"):
        row.failed_runs = int(row.failed_runs or 0) + 1
        # Phase 5: schedule review after enough struggle
        if row.failed_runs >= 3 or row.hints_used >= 2:
            row.next_review_at = datetime.now(UTC) + timedelta(days=1)
        await session.commit()
        return {
            "ok": False,
            "error": outcome.get("error") or "Not quite.",
            "error_line": outcome.get("error_line"),
            "stars": int(row.stars or 0),
            "xp_awarded": 0,
            "completed": row.status == "completed",
        }

    lines = count_code_lines(code)
    earned_stars = stars_for_lines(lines, level.par_lines)
    already = row.status == "completed"
    awarded = 0
    if not already:
        row.status = "completed"
        row.completed_at = datetime.now(UTC)
        row.stars = earned_stars
        row.best_lines = lines
        stats = await _stats_for(session, user.id)
        awarded = max(0, int(level.xp) - int(row.hints_used or 0) * 2)
        stats.xp += awarded
    else:
        if row.best_lines is None or lines < row.best_lines:
            row.best_lines = lines
        if earned_stars > int(row.stars or 0):
            row.stars = earned_stars
    # Clear review when freshly cleared well
    if row.failed_runs >= 3 or row.hints_used >= 2:
        row.next_review_at = datetime.now(UTC) + timedelta(days=3)
    await session.commit()
    stats = await _stats_for(session, user.id)
    return {
        "ok": True,
        "error": None,
        "error_line": None,
        "stars": int(row.stars or 0),
        "earned_stars": earned_stars,
        "lines": lines,
        "par_lines": level.par_lines,
        "xp_awarded": awarded,
        "xp_total": stats.xp,
        "completed": True,
        "first_clear": not already,
    }


async def admin_list_levels(session: AsyncSession) -> list[dict]:
    rows = list(
        (
            await session.scalars(
                select(GhostwalkLevel).order_by(GhostwalkLevel.position, GhostwalkLevel.slug)
            )
        ).all()
    )
    return [_admin_level(row) for row in rows]


def _admin_level(level: GhostwalkLevel) -> dict:
    return {
        "id": level.id,
        "slug": level.slug,
        "order": level.position,
        "title": level.title,
        "concept": level.concept,
        "intro_markdown": level.intro_markdown,
        "grid": level.grid,
        "start": level.start,
        "allowed": level.allowed,
        "goal": level.goal,
        "max_steps": level.max_steps,
        "mode": level.mode,
        "starter_code": level.starter_code,
        "solution": level.solution,
        "hints": level.hints,
        "par_lines": level.par_lines,
        "xp": level.xp,
        "status": level.status,
        "python_lesson_slug": level.python_lesson_slug,
    }


async def admin_upsert_level(
    session: AsyncSession,
    payload: dict,
    *,
    level_id: uuid.UUID | None = None,
    match_slug: bool = False,
) -> dict:
    errors = validate_level_payload(payload)
    if errors:
        raise ContentError(400, "; ".join(errors))
    slug = str(payload.get("slug") or "").strip()
    if not slug:
        raise ContentError(400, "slug is required")
    level: GhostwalkLevel | None = None
    if level_id:
        level = await session.get(GhostwalkLevel, level_id)
        if level is None:
            raise ContentError(404, "Level not found")
    elif match_slug:
        level = await session.scalar(select(GhostwalkLevel).where(GhostwalkLevel.slug == slug))
    else:
        clash = await session.scalar(select(GhostwalkLevel).where(GhostwalkLevel.slug == slug))
        if clash:
            raise ContentError(409, "That slug is already used")
    if level is None:
        level = GhostwalkLevel(
            slug=slug,
            position=0,
            title=slug,
            grid=[],
            start={},
            allowed=[],
            goal={},
            hints=[],
        )
        session.add(level)
    level.slug = slug
    level.position = int(payload.get("order") or payload.get("position") or level.position or 0)
    level.title = str(payload.get("title") or slug)[:120]
    level.concept = str(payload.get("concept") or "")[:120]
    level.intro_markdown = str(payload.get("intro_markdown") or "")
    level.grid = payload.get("grid") or []
    level.start = payload.get("start") or {}
    level.allowed = list(payload.get("allowed") or [])
    level.goal = dict(payload.get("goal") or {"reach_goal": True})
    level.max_steps = int(payload.get("max_steps") or 500)
    level.mode = str(payload.get("mode") or "free")
    level.starter_code = str(payload.get("starter_code") or "")
    level.solution = str(payload.get("solution") or "")
    level.hints = list(payload.get("hints") or [])
    level.par_lines = max(1, int(payload.get("par_lines") or 1))
    level.xp = int(payload.get("xp") or 20)
    level.status = str(payload.get("status") or "draft")
    level.python_lesson_slug = payload.get("python_lesson_slug")
    await session.commit()
    await session.refresh(level)
    return _admin_level(level)


def parse_import_document(raw: str | dict) -> list[dict]:
    """Accept YAML/JSON text or a dict with levels / a single level."""
    if isinstance(raw, dict):
        loaded = raw
    else:
        text = str(raw or "").strip()
        if not text:
            raise ContentError(400, "Import document is empty.")
        try:
            loaded = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ContentError(400, f"Invalid YAML: {exc}") from exc
    if loaded is None:
        raise ContentError(400, "Import document is empty.")
    if isinstance(loaded, list):
        rows = loaded
    elif isinstance(loaded, dict):
        if isinstance(loaded.get("levels"), list):
            rows = loaded["levels"]
        elif loaded.get("slug"):
            rows = [loaded]
        else:
            raise ContentError(400, "Expected a levels list or a single level with a slug.")
    else:
        raise ContentError(400, "Expected YAML/JSON object or list.")
    out = [item for item in rows if isinstance(item, dict)]
    if not out:
        raise ContentError(400, "No level objects found in the file.")
    return out


async def admin_import_levels(
    session: AsyncSession,
    *,
    document: str | dict,
    dry_run: bool = True,
    publish: bool = False,
) -> dict:
    rows = parse_import_document(document)
    preview: list[dict] = []
    for item in rows:
        errors = validate_level_payload(item)
        slug = str(item.get("slug") or "").strip()
        existing = None
        if slug:
            existing = await session.scalar(
                select(GhostwalkLevel).where(GhostwalkLevel.slug == slug)
            )
        preview.append(
            {
                "slug": slug or None,
                "title": item.get("title"),
                "ok": not errors,
                "errors": errors,
                "action": "update" if existing else "create",
            }
        )
    if dry_run:
        return {
            "dry_run": True,
            "count": len(preview),
            "ok_count": sum(1 for item in preview if item["ok"]),
            "preview": preview,
        }

    created = 0
    updated = 0
    skipped = 0
    for item, row in zip(rows, preview, strict=True):
        if not row["ok"]:
            skipped += 1
            continue
        payload = dict(item)
        if publish:
            payload["status"] = "published"
        slug = str(payload.get("slug") or "").strip()
        before = await session.scalar(
            select(GhostwalkLevel).where(GhostwalkLevel.slug == slug)
        )
        await admin_upsert_level(session, payload, match_slug=True)
        if before:
            updated += 1
        else:
            created += 1
    return {
        "dry_run": False,
        "count": len(preview),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "preview": preview,
    }


async def admin_reorder(session: AsyncSession, ordered_ids: list[uuid.UUID]) -> list[dict]:
    rows = list((await session.scalars(select(GhostwalkLevel))).all())
    by_id = {row.id: row for row in rows}
    for index, level_id in enumerate(ordered_ids, start=1):
        if level_id in by_id:
            by_id[level_id].position = index
    await session.commit()
    return await admin_list_levels(session)


async def admin_test_solution(session: AsyncSession, level_id: uuid.UUID) -> dict:
    level = await session.get(GhostwalkLevel, level_id)
    if level is None:
        raise ContentError(404, "Level not found")
    from app.ghostwalk.world import run_learner_code

    ran = run_learner_code(level_dict(level), level.solution or "")
    if not ran.get("ok"):
        return {"ok": False, "error": ran.get("error"), "actions": ran.get("actions") or []}
    checked = replay(level_dict(level), ran.get("actions") or [])
    return {
        "ok": bool(checked.get("ok")),
        "error": checked.get("error"),
        "actions": ran.get("actions") or [],
        "trace": ran.get("trace") or [],
    }


async def home_continue(session: AsyncSession, user: User) -> dict | None:
    board = await list_levels_for_user(session, user)
    if not board.get("continue") and board.get("solved", 0) == 0:
        # Only show if they have started something
        progress_count = await session.scalar(
            select(func.count())
            .select_from(GhostwalkProgress)
            .where(GhostwalkProgress.user_id == user.id)
        )
        if not progress_count:
            return None
    cont = board.get("continue")
    if cont:
        return {
            "slug": cont["slug"],
            "title": cont["title"],
            "order": cont["order"],
            "label": f"Ghostwalk · Level {cont['order']} · {cont['title']}",
        }
    return None
