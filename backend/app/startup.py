"""Apply migrations, then bootstrap or print a setup token when needed."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker
from app.services.seed import seed_starter_content
from app.services.setup import ensure_setup_token, maybe_bootstrap_admin
from app.services.tracks import ensure_tracks


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
    return cfg


async def run_migrations() -> None:
    cfg = _alembic_config()
    await asyncio.to_thread(command.upgrade, cfg, "head")


async def startup() -> None:
    await run_migrations()
    async with get_sessionmaker()() as session:
        await ensure_tracks(session)
        await seed_starter_content(session)
        # DECISION: bootstrap wins when enabled; otherwise print a one-time
        # setup token for the interactive /setup form.
        if not await maybe_bootstrap_admin(session):
            await ensure_setup_token(session)


async def shutdown() -> None:
    await dispose_engine()
