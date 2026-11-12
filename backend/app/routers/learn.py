"""Tracks and published lessons a signed-in user is allowed to open."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.track import Track
from app.models.user import User
from app.schemas.users import TrackOut
from app.security.deps import current_user, require_track_access
from app.services.boss import (
    check_boss_item,
    finish_boss,
    open_hint,
    reveal_boss_item,
    start_boss,
)
from app.services.content_store import (
    ContentError,
    lesson_for_learner,
    outline_for,
    projects_for_user,
)
from app.services.progress import dashboard, lesson_states, progress_for_exercises
from app.services.tracks import list_visible_tracks

router = APIRouter(prefix="/learn", tags=["learn"])


class BossHintIn(BaseModel):
    exercise_id: UUID
    level: int = Field(ge=1, le=6)


class BossCheckIn(BaseModel):
    exercise_id: UUID
    attempt: str = Field(default="", max_length=20000)


class BossRevealIn(BaseModel):
    exercise_id: UUID


def _track_out(track: Track) -> TrackOut:
    return TrackOut(
        slug=track.slug,
        name=track.name,
        description=track.description,
        icon=track.icon,
        color=track.color,
        order=track.position,
    )


@router.get("/dashboard")
async def learn_dashboard(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await dashboard(db, user)


@router.get("/projects")
async def learn_projects(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    body = await projects_for_user(db, user)
    states = await lesson_states(db, user.id, [item["id"] for item in body["projects"]])
    for item in body["projects"]:
        item["progress"] = states.get(item["id"], "new")
    return body


@router.get("/tracks", response_model=list[TrackOut])
async def tracks(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrackOut]:
    rows = await list_visible_tracks(db, user)
    return [_track_out(track) for track in rows]


@router.get("/tracks/{slug}", response_model=TrackOut)
async def track(row: Track = Depends(require_track_access)) -> TrackOut:
    return _track_out(row)


@router.get("/tracks/{slug}/outline")
async def outline(
    row: Track = Depends(require_track_access),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.gating import module_gate_state

    body = await outline_for(db, row)
    lesson_ids = [lesson["id"] for module in body["modules"] for lesson in module["lessons"]]
    states = await lesson_states(db, user.id, lesson_ids)
    gates = {item["module_id"]: item for item in await module_gate_state(db, user, row.id)}
    await db.commit()
    for module in body["modules"]:
        gate = gates.get(module["id"]) or {}
        module["unlocked"] = gate.get("unlocked", True)
        module["mastered"] = gate.get("mastered", False)
        module["lock_reason"] = gate.get("lock_reason")
        module["recall_done"] = gate.get("recall_done", 0)
        module["recall_total"] = gate.get("recall_total", 0)
        module["needed"] = gate.get("needed", 0)
        for lesson in module["lessons"]:
            lesson["progress"] = states.get(lesson["id"], "new")
    return body


@router.get("/lessons/{lesson_id}")
async def lesson(
    lesson_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        payload = await lesson_for_learner(db, user, lesson_id)
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    states = await progress_for_exercises(
        db, user.id, [item["id"] for item in payload["exercises"]]
    )
    for item in payload["exercises"]:
        item["progress"] = states.get(item["id"])
    return payload


@router.post("/modules/{module_id}/boss/start")
async def module_boss_start(
    module_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await start_boss(db, user, module_id)
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/modules/{module_id}/boss/{run_id}/hint")
async def module_boss_hint(
    module_id: UUID,
    run_id: UUID,
    payload: BossHintIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await open_hint(
            db,
            user,
            module_id,
            run_id,
            exercise_id=payload.exercise_id,
            level=payload.level,
        )
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/modules/{module_id}/boss/{run_id}/check")
async def module_boss_check(
    module_id: UUID,
    run_id: UUID,
    payload: BossCheckIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await check_boss_item(
            db,
            user,
            module_id,
            run_id,
            exercise_id=payload.exercise_id,
            attempt=payload.attempt,
        )
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/modules/{module_id}/boss/{run_id}/reveal")
async def module_boss_reveal(
    module_id: UUID,
    run_id: UUID,
    payload: BossRevealIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await reveal_boss_item(
            db,
            user,
            module_id,
            run_id,
            exercise_id=payload.exercise_id,
        )
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/modules/{module_id}/boss/{run_id}/finish")
async def module_boss_finish(
    module_id: UUID,
    run_id: UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await finish_boss(db, user, module_id, run_id)
    except ContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
