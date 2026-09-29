"""Create and edit notification channels. Secrets stay encrypted."""

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationChannel
from app.security.crypto import SecretError, decrypt_secret, encrypt_secret
from app.services.audit import write_audit
from app.services.notifications.dispatcher import deliver_one, public_error
from app.services.notifications.fields import (
    EMAIL_PROVIDERS,
    ConfigError,
    public_config,
    secret_names,
    validate_config,
)

KEY_ERROR = "APP_ENCRYPTION_KEY cannot encrypt notification settings"


class ChannelError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def pack(config: dict) -> str:
    try:
        return encrypt_secret(json.dumps(config))
    except SecretError as exc:
        raise ChannelError(500, KEY_ERROR) from exc


def unpack(ciphertext: str) -> dict:
    try:
        loaded = json.loads(decrypt_secret(ciphertext))
    except SecretError as exc:
        raise ChannelError(500, KEY_ERROR) from exc
    if not isinstance(loaded, dict):
        raise ChannelError(500, KEY_ERROR)
    return loaded


def merge_config(provider: str, incoming: dict, stored: dict | None) -> dict:
    """Keep a saved secret when the form sends it back blank."""
    merged = dict(incoming)
    previous = stored or {}
    for name in secret_names(provider):
        value = incoming.get(name)
        if value in (None, "", "••••••") and previous.get(name):
            merged[name] = previous[name]
    try:
        return validate_config(provider, merged)
    except ConfigError as exc:
        raise ChannelError(400, exc.detail) from exc


def _row_out(row: NotificationChannel, config: dict) -> dict:
    visible, secrets = public_config(row.provider, config)
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "events": list(row.events or []),
        "is_enabled": row.is_enabled,
        "config": visible,
        "secrets": secrets,
        "last_test_at": row.last_test_at,
        "last_test_ok": row.last_test_ok,
    }


async def list_channels(session: AsyncSession) -> dict:
    rows = list(
        (
            await session.scalars(
                select(NotificationChannel).order_by(NotificationChannel.created_at)
            )
        ).all()
    )
    channels = []
    email_ready = False
    for row in rows:
        try:
            config = unpack(row.config_encrypted)
        except ChannelError:
            config = {}
        if row.is_enabled and row.provider in EMAIL_PROVIDERS and config:
            email_ready = True
        channels.append(_row_out(row, config))
    return {"channels": channels, "email_channel_ready": email_ready}


async def create_channel(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    name: str,
    provider: str,
    events: list[str],
    is_enabled: bool,
    config: dict,
    ip: str | None,
) -> dict:
    cleaned = merge_config(provider, config, None)
    row = NotificationChannel(
        name=name,
        provider=provider,
        config_encrypted=pack(cleaned),
        events=events,
        is_enabled=is_enabled,
    )
    session.add(row)
    await session.flush()
    await write_audit(
        session,
        actor_user_id=actor_id,
        action="notification.create",
        target_type="notification_channel",
        target_id=str(row.id),
        details={"name": name, "provider": provider, "events": events},
        ip=ip,
    )
    await session.commit()
    return _row_out(row, cleaned)


async def update_channel(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    channel_id: uuid.UUID,
    name: str,
    provider: str,
    events: list[str],
    is_enabled: bool,
    config: dict,
    ip: str | None,
) -> dict:
    row = await session.get(NotificationChannel, channel_id)
    if row is None:
        raise ChannelError(404, "Channel not found")
    stored = unpack(row.config_encrypted) if row.provider == provider else None
    cleaned = merge_config(provider, config, stored)
    row.name = name
    row.provider = provider
    row.events = events
    row.is_enabled = is_enabled
    row.config_encrypted = pack(cleaned)
    await write_audit(
        session,
        actor_user_id=actor_id,
        action="notification.update",
        target_type="notification_channel",
        target_id=str(row.id),
        details={"name": name, "provider": provider, "events": events, "is_enabled": is_enabled},
        ip=ip,
    )
    await session.commit()
    return _row_out(row, cleaned)


async def delete_channel(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    channel_id: uuid.UUID,
    ip: str | None,
) -> None:
    row = await session.get(NotificationChannel, channel_id)
    if row is None:
        raise ChannelError(404, "Channel not found")
    name = row.name
    provider = row.provider
    await session.delete(row)
    await write_audit(
        session,
        actor_user_id=actor_id,
        action="notification.delete",
        target_type="notification_channel",
        target_id=str(channel_id),
        details={"name": name, "provider": provider},
        ip=ip,
    )
    await session.commit()


async def send_test(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    channel_id: uuid.UUID,
    ip: str | None,
) -> dict:
    row = await session.get(NotificationChannel, channel_id)
    if row is None:
        raise ChannelError(404, "Channel not found")
    config = unpack(row.config_encrypted)
    ok = True
    detail = "Test message sent."
    try:
        await deliver_one(row.provider, config, "notification.test", {})
    except Exception as exc:
        ok = False
        detail = public_error(exc)
    row.last_test_at = datetime.now(UTC)
    row.last_test_ok = ok
    await write_audit(
        session,
        actor_user_id=actor_id,
        action="notification.test",
        target_type="notification_channel",
        target_id=str(row.id),
        details={"ok": ok, "provider": row.provider, "name": row.name},
        ip=ip,
    )
    await session.commit()
    return {"ok": ok, "detail": detail}
