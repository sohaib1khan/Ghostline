"""Read and update learner accessibility preferences."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.schemas.preferences import PreferencesIn, PreferencesOut
from app.services.audit import write_audit

DEFAULTS = PreferencesOut().model_dump()


def normalize_preferences(raw: dict | None) -> dict:
    merged = {**DEFAULTS, **(raw or {})}
    return PreferencesOut.model_validate(merged).model_dump()


async def read_preferences(user: User) -> dict:
    return normalize_preferences(user.preferences if isinstance(user.preferences, dict) else {})


async def update_preferences(
    session: AsyncSession,
    user: User,
    payload: PreferencesIn,
    *,
    ip: str | None,
) -> dict:
    current = await read_preferences(user)
    patch = payload.model_dump(exclude_none=True)
    next_prefs = normalize_preferences({**current, **patch})
    user.preferences = next_prefs
    flag_modified(user, "preferences")
    await write_audit(
        session,
        actor_user_id=user.id,
        action="preferences.update",
        target_type="user",
        target_id=str(user.id),
        details={"keys": sorted(patch.keys())},
        ip=ip,
    )
    await session.commit()
    await session.refresh(user)
    return next_prefs
