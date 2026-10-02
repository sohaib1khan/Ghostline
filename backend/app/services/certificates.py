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


async def _completion_for_track(
    session: AsyncSession, user_id: uuid.UUID, track_id: uuid.UUID
) -> dict:
    exercise_ids = await _published_exercise_ids(session, track_id)
    total = len(exercise_ids)
    if total == 0:
        return {
            "total": 0,
            "completed": 0,
            "complete": False,
            "completed_at": None,
        }
    done_rows = list(
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
    done = len(done_rows)
    latest = None
    for _exercise_id, completed_at in done_rows:
        if completed_at is None:
            continue
        stamp = completed_at.date() if isinstance(completed_at, datetime) else completed_at
        if latest is None or stamp > latest:
            latest = stamp
    return {
        "total": total,
        "completed": done,
        "complete": done >= total,
        "completed_at": latest,
    }


def _render_body(template: str, track_name: str) -> str:
    return template.replace("{track}", track_name)


async def list_certificates(session: AsyncSession, user: User) -> dict:
    config = await get_certificate_config(session)
    tracks = await list_visible_tracks(session, user)
    items = []
    for track in tracks:
        progress = await _completion_for_track(session, user.id, track.id)
        earned = bool(config["enabled"] and progress["complete"] and progress["total"] > 0)
        completed_on = progress["completed_at"] or datetime.now(UTC).date()
        items.append(
            {
                "track_slug": track.slug,
                "track_name": track.name,
                "track_color": track.color,
                "enabled": config["enabled"],
                "total": progress["total"],
                "completed": progress["completed"],
                "complete": progress["complete"],
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
    if progress["total"] == 0:
        raise ContentError(404, "This track has no published lessons yet")

    earned = bool(progress["complete"])
    completed_on = progress["completed_at"] or datetime.now(UTC).date()
    return {
        "enabled": True,
        "track_slug": track.slug,
        "track_name": track.name,
        "track_color": track.color,
        "learner_name": _learner_name(user),
        "total": progress["total"],
        "completed": progress["completed"],
        "complete": progress["complete"],
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
