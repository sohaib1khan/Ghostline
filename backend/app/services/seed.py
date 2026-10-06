"""Load starter lessons once, from backend/app/seed/lessons."""

from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Lesson, Module
from app.models.track import Track
from app.services.content_io import import_documents, parse_document
from app.services.settings_store import get_setting, set_setting
from app.services.tracks import ensure_tracks

SEEDED_KEY = "content_seeded"
# DECISION: a lock so two processes starting together do not both import.
SEED_LOCK_ID = 4815162345


def _lesson_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "seed" / "lessons"


def _addon_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "seed" / "addons"


async def _import_file(session: AsyncSession, path: Path, *, mode: str = "replace") -> None:
    document = path.read_text(encoding="utf-8")
    parse_document(document)
    await import_documents(
        session,
        actor_id=None,
        document=document,
        dry_run=False,
        ip=None,
        commit=False,
        mode=mode,
    )


async def _import_tracks_without_modules(session: AsyncSession) -> None:
    # DECISION: a later track file is imported when that track has no modules.
    # Tracks that already have lessons are left alone.
    for path in sorted(_lesson_dir().glob("*.yaml")):
        loaded = parse_document(path.read_text(encoding="utf-8"))
        slug = str(loaded.get("slug") or "")
        track = await session.scalar(select(Track).where(Track.slug == slug))
        if track is None:
            continue
        modules = await session.scalar(
            select(func.count()).select_from(Module).where(Module.track_id == track.id)
        )
        if modules:
            continue
        await _import_file(session, path)


def _catalog_parts(loaded: dict) -> list[dict]:
    if "tracks" in loaded:
        return list(loaded.get("tracks") or [])
    return [loaded]


async def _addon_needs_import(session: AsyncSession, loaded: dict) -> bool:
    # Only extend when a named module from the addon is still missing.
    # Matching modules are left alone so admin edits survive restarts.
    for part in _catalog_parts(loaded):
        slug = str(part.get("slug") or "")
        track = await session.scalar(
            select(Track)
            .where(Track.slug == slug)
            .options(selectinload(Track.modules))
        )
        if track is None:
            continue
        titles = {module.title.strip() for module in track.modules}
        for module in part.get("modules") or []:
            title = str(module.get("title") or "").strip()
            if title and title not in titles:
                return True
    return False


async def _import_addons(session: AsyncSession) -> None:
    addon_dir = _addon_dir()
    if not addon_dir.is_dir():
        return
    for path in sorted(addon_dir.glob("*.yaml")):
        loaded = parse_document(path.read_text(encoding="utf-8"))
        if not await _addon_needs_import(session, loaded):
            continue
        await _import_file(session, path, mode="extend")


def _strip_level_prefix(description: str) -> str:
    text = (description or "").strip()
    for prefix in ("Beginner — ", "Intermediate — ", "Advanced — ", "Beginner - ", "Intermediate - ", "Advanced - "):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


async def _label_module_levels(session: AsyncSession) -> None:
    """Keep published module descriptions tagged for the learn path."""
    from app.services.content_store import _assign_module_levels

    tracks = list((await session.scalars(select(Track).order_by(Track.position))).all())
    for track in tracks:
        modules = list(
            (
                await session.scalars(
                    select(Module)
                    .where(Module.track_id == track.id, Module.status == "published")
                    .options(selectinload(Module.lessons))
                    .order_by(Module.position)
                )
            ).all()
        )
        if not modules:
            continue
        leveled = _assign_module_levels(modules)
        labels = {
            "beginner": "Beginner",
            "intermediate": "Intermediate",
            "advanced": "Advanced",
        }
        by_id = {item["id"]: item for item in leveled}
        for module in modules:
            band = by_id.get(module.id)
            if band is None:
                continue
            label = labels[band["level"]]
            rest = _strip_level_prefix(module.description or "")
            wanted = f"{label} — {rest}" if rest else f"{label} — keep typing."
            if module.description != wanted:
                module.description = wanted


async def _clear_challenge_timers(session: AsyncSession) -> None:
    # DECISION: challenge / daily-script drills stay untimed. A leftover limit of
    # 0 also made the learner UI treat the round as already expired.
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.content import Exercise

    rows = list((await session.scalars(select(Exercise).where(Exercise.type == "challenge"))).all())
    for row in rows:
        data = dict(row.data or {})
        if data.get("time_limit_seconds"):
            data["time_limit_seconds"] = None
            row.data = data
            flag_modified(row, "data")


async def seed_starter_content(session: AsyncSession) -> None:
    # Tracks are created here so the first admin setup can import lessons
    # even when this process never ran the startup seed.
    await ensure_tracks(session)
    await session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": SEED_LOCK_ID})
    if not await get_setting(session, SEEDED_KEY):
        existing = await session.scalar(select(func.count()).select_from(Lesson))
        if not existing:
            for path in sorted(_lesson_dir().glob("*.yaml")):
                await _import_file(session, path)
        await set_setting(session, SEEDED_KEY, {"seeded": True})
    await _import_tracks_without_modules(session)
    await _import_addons(session)
    await _label_module_levels(session)
    await _clear_challenge_timers(session)
    await session.commit()
