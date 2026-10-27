"""Course certificates — preview with watermark, full award on track completion."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Exercise, Lesson, Module
from app.models.progress import ExerciseProgress
from app.models.track import Track, UserTrackAccess
from app.models.user import User
from app.security.roles import is_staff
from app.services.content_store import ContentError
from app.services.settings_store import get_setting, set_setting
from app.services.tracks import list_visible_tracks

CERTIFICATE_KEY = "certificate_config"

DEFAULT_CONFIG = {
    "enabled": True,
    "title": "Certificate of Completion",
    "subtitle": "This certifies that",
    "body": "has successfully completed the {track} learning path.",
    "signer_name": "Ghostline",
    "signer_title": "Typing-first practice",
    "footer": "Keep typing. Keep the muscle memory.",
}


def _normalize_config(stored) -> dict:
    base = dict(DEFAULT_CONFIG)
    if isinstance(stored, dict):
        for key in DEFAULT_CONFIG:
            if key not in stored:
                continue
            if key == "enabled":
                base[key] = bool(stored[key])
            else:
                value = str(stored[key] or "").strip()
                if value:
                    base[key] = value[:240]
    return base


async def get_certificate_config(session: AsyncSession) -> dict:
    return _normalize_config(await get_setting(session, CERTIFICATE_KEY))


async def save_certificate_config(session: AsyncSession, payload: dict) -> dict:
    config = _normalize_config(
        {
            "enabled": bool(payload.get("enabled")),
            "title": payload.get("title"),
            "subtitle": payload.get("subtitle"),
            "body": payload.get("body"),
            "signer_name": payload.get("signer_name"),
            "signer_title": payload.get("signer_title"),
            "footer": payload.get("footer"),
        }
    )
    await set_setting(session, CERTIFICATE_KEY, config)
    return config


def _learner_name(user: User) -> str:
    return f"{user.first_name} {user.last_name}".strip()


def _certificate_code(user_id: uuid.UUID, track_slug: str, completed_on: date) -> str:
    digest = hashlib.sha256(
        f"{user_id}:{track_slug}:{completed_on.isoformat()}".encode()
    ).hexdigest()[:8].upper()
    return f"GL-{track_slug.upper()[:6]}-{digest}"


def _pct(completed: int, total: int) -> int:
    if total <= 0:
        return 0
    return min(100, round((completed / total) * 100))


async def _published_exercise_ids(
    session: AsyncSession, track_id: uuid.UUID
) -> list[uuid.UUID]:
    rows = list(
        (
            await session.execute(
                select(Exercise.id)
                .join(Lesson, Lesson.id == Exercise.lesson_id)
                .join(Module, Module.id == Lesson.module_id)
                .where(
                    Module.track_id == track_id,
                    Module.status == "published",
                    Lesson.status == "published",
                    Exercise.status == "published",
                )
            )
        ).all()
    )
    return [row[0] for row in rows]


async def _module_boss_completion(
    session: AsyncSession, user_id: uuid.UUID, track_id: uuid.UUID
) -> dict:
    """Module bosses still gate mastery on each published module."""
    from app.models.module_progress import ModuleProgress

    modules = list(
        (
            await session.scalars(
                select(Module)
                .where(Module.track_id == track_id, Module.status == "published")
                .order_by(Module.position)
            )
        ).all()
    )
    total = len(modules)
    if total == 0:
        return {
            "total": 0,
            "completed": 0,
            "complete": True,
            "completed_at": None,
        }
    rows = list(
        (
            await session.scalars(
                select(ModuleProgress).where(
                    ModuleProgress.user_id == user_id,
                    ModuleProgress.module_id.in_([module.id for module in modules]),
                    ModuleProgress.mastered_at.is_not(None),
                )
            )
        ).all()
    )
    done = len(rows)
    latest = None
    for row in rows:
        if row.mastered_at is None:
            continue
        stamp = row.mastered_at.date()
        if latest is None or stamp > latest:
            latest = stamp
    return {
        "total": total,
        "completed": done,
        "complete": done >= total,
        "completed_at": latest,
    }


async def _completion_for_track(
    session: AsyncSession, user_id: uuid.UUID, track_id: uuid.UUID
) -> dict:
    """Earn when every published exercise is complete and every module boss is passed."""
    bosses = await _module_boss_completion(session, user_id, track_id)
    exercise_ids = await _published_exercise_ids(session, track_id)
    exercise_total = len(exercise_ids)
    done_rows = (
        list(
            (
                await session.execute(
                    select(ExerciseProgress.exercise_id, ExerciseProgress.completed_at)
                    .where(
                        ExerciseProgress.user_id == user_id,
                        ExerciseProgress.exercise_id.in_(exercise_ids),
                        ExerciseProgress.status == "completed",
                    )
                )
            ).all()
        )
        if exercise_ids
        else []
    )
    exercises_completed = len(done_rows)
    exercises_pct = _pct(exercises_completed, exercise_total)
    bosses_pct = _pct(bosses["completed"], bosses["total"])
    # Overall rate weights exercises first (what learners see day to day).
    if exercise_total > 0 and bosses["total"] > 0:
        percent = round((exercises_pct * 0.7) + (bosses_pct * 0.3))
    elif exercise_total > 0:
        percent = exercises_pct
    else:
        percent = bosses_pct

    exercise_dates = [row[1].date() for row in done_rows if row[1] is not None]
    latest_exercise = max(exercise_dates) if exercise_dates else None
    completed_at = bosses["completed_at"] or latest_exercise
    if bosses["completed_at"] and latest_exercise:
        completed_at = max(bosses["completed_at"], latest_exercise)

    exercises_done = exercise_total > 0 and exercises_completed >= exercise_total
    bosses_done = bosses["complete"]
    complete = exercises_done and bosses_done and exercise_total > 0

    return {
        "total": exercise_total,
        "completed": exercises_completed,
        "percent": percent,
        "exercises_total": exercise_total,
        "exercises_completed": exercises_completed,
        "exercises_percent": exercises_pct,
        "bosses_total": bosses["total"],
        "bosses_completed": bosses["completed"],
        "bosses_percent": bosses_pct,
        "complete": complete,
        "completed_at": completed_at,
        "bosses_required": bosses["total"] > 0,
    }


def _render_body(template: str, track_name: str) -> str:
    return template.replace("{track}", track_name)


def _progress_fields(progress: dict) -> dict:
    return {
        "total": progress["total"],
        "completed": progress["completed"],
        "percent": progress["percent"],
        "exercises_total": progress["exercises_total"],
        "exercises_completed": progress["exercises_completed"],
        "exercises_percent": progress["exercises_percent"],
        "bosses_total": progress["bosses_total"],
        "bosses_completed": progress["bosses_completed"],
        "bosses_percent": progress["bosses_percent"],
        "complete": progress["complete"],
        "bosses_required": progress["bosses_required"],
    }


async def list_certificates(session: AsyncSession, user: User) -> dict:
    config = await get_certificate_config(session)
    tracks = await list_visible_tracks(session, user)
    items = []
    for track in tracks:
        progress = await _completion_for_track(session, user.id, track.id)
        earned = bool(config["enabled"] and progress["complete"])
        completed_on = progress["completed_at"] or datetime.now(UTC).date()
        items.append(
            {
                "track_slug": track.slug,
                "track_name": track.name,
                "track_color": track.color,
                "enabled": config["enabled"],
                **_progress_fields(progress),
                "earned": earned,
                "watermarked": not earned,
                "completed_at": (
                    progress["completed_at"].isoformat() if progress["completed_at"] else None
                ),
                "code": (
                    _certificate_code(user.id, track.slug, completed_on) if earned else None
                ),
            }
        )
    return {
        "enabled": config["enabled"],
        "learner_name": _learner_name(user),
        "certificates": items,
    }


async def certificate_for_track(session: AsyncSession, user: User, slug: str) -> dict:
    config = await get_certificate_config(session)
    if not config["enabled"]:
        raise ContentError(404, "Certificates are turned off")

    tracks = await list_visible_tracks(session, user)
    track = next((item for item in tracks if item.slug == slug), None)
    if track is None:
        # Staff can still open any active track for preview.
        if is_staff(user.role):
            track = await session.scalar(
                select(Track).where(Track.slug == slug, Track.is_active.is_(True))
            )
        if track is None:
            raise ContentError(404, "Track not found")
        if not is_staff(user.role):
            access = await session.scalar(
                select(UserTrackAccess.id).where(
                    UserTrackAccess.user_id == user.id,
                    UserTrackAccess.track_id == track.id,
                )
            )
            if access is None:
                raise ContentError(403, "You do not have access to this track")

    progress = await _completion_for_track(session, user.id, track.id)
    if progress["exercises_total"] == 0 and progress["bosses_total"] == 0:
        raise ContentError(404, "This track has no published lessons yet")

    earned = bool(progress["complete"])
    completed_on = progress["completed_at"] or datetime.now(UTC).date()
    return {
        "enabled": True,
        "track_slug": track.slug,
        "track_name": track.name,
        "track_color": track.color,
        "learner_name": _learner_name(user),
        **_progress_fields(progress),
        "earned": earned,
        "watermarked": not earned,
        "completed_at": progress["completed_at"].isoformat() if progress["completed_at"] else None,
        "issued_on": completed_on.isoformat() if earned else None,
        "code": _certificate_code(user.id, track.slug, completed_on) if earned else None,
        "title": config["title"],
        "subtitle": config["subtitle"],
        "body": _render_body(config["body"], track.name),
        "signer_name": config["signer_name"],
        "signer_title": config["signer_title"],
        "footer": config["footer"],
    }
