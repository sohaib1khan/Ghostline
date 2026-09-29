"""Fan out events after the account action has already committed."""

import asyncio
import logging

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models.notification import NotificationChannel
from app.services.audit import write_audit
from app.services.notifications.base import DeliveryError
from app.services.notifications.fields import EMAIL_PROVIDERS
from app.services.notifications.messages import build_message, recipient_for
from app.services.notifications.registry import SENDERS

logger = logging.getLogger("ghostline.notifications")

_tasks: set[asyncio.Task] = set()


def public_error(exc: BaseException) -> str:
    if isinstance(exc, DeliveryError):
        return str(exc)[:200]
    return "Delivery failed"


async def deliver_one(provider: str, config: dict, event: str, payload: dict) -> None:
    recipient = recipient_for(provider, event, config, payload)
    if provider in EMAIL_PROVIDERS and not recipient:
        raise DeliveryError("No recipient address")
    message = build_message(event, payload, recipient=recipient)
    sender = SENDERS.get(provider)
    if sender is None:
        raise DeliveryError("Unknown provider")
    await sender(config, message)


async def dispatch_event(event: str, payload: dict) -> None:
    # DECISION: the account action has already committed. Delivery runs in the
    # background so a slow or down channel cannot hold signup or approval.
    task = asyncio.create_task(_deliver(event, dict(payload)))
    _tasks.add(task)
    task.add_done_callback(_done)


def _done(task: asyncio.Task) -> None:
    _tasks.discard(task)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.warning("notification fan-out failed: %s", type(error).__name__)


async def flush_notifications() -> None:
    pending = list(_tasks)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def _deliver(event: str, payload: dict) -> None:
    try:
        jobs = await _jobs(event)
        failures: list[tuple] = []
        for channel_id, provider, config_or_error in jobs:
            if isinstance(config_or_error, Exception):
                failures.append((channel_id, provider, public_error(config_or_error)))
                continue
            try:
                await deliver_one(provider, config_or_error, event, payload)
            except Exception as exc:
                failures.append((channel_id, provider, public_error(exc)))
        if failures:
            await _record_failures(event, failures)
    except Exception as error:
        # DECISION: log the exception type only. Tracebacks from SMTP and HTTP
        # clients can include a password or a response body.
        logger.warning("notification fan-out failed: %s", type(error).__name__)


async def _jobs(event: str) -> list[tuple]:
    from app.services.notifications.channels import unpack

    async with get_sessionmaker()() as session:
        rows = list(
            (
                await session.scalars(
                    select(NotificationChannel).where(NotificationChannel.is_enabled.is_(True))
                )
            ).all()
        )
        jobs = []
        for row in rows:
            if event not in (row.events or []):
                continue
            try:
                config = unpack(row.config_encrypted)
            except Exception as exc:
                jobs.append((row.id, row.provider, exc))
                continue
            jobs.append((row.id, row.provider, config))
        return jobs


async def _record_failures(event: str, failures: list[tuple]) -> None:
    async with get_sessionmaker()() as session:
        for channel_id, provider, error in failures:
            logger.warning(
                "notification delivery failed channel=%s provider=%s event=%s",
                channel_id,
                provider,
                event,
            )
            await write_audit(
                session,
                actor_user_id=None,
                action="notification.delivery_failed",
                target_type="notification_channel",
                target_id=str(channel_id),
                details={
                    "channel_id": str(channel_id),
                    "provider": provider,
                    "event": event,
                    "error": error,
                },
            )
        await session.commit()
