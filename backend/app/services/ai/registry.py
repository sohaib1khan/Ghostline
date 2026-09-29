"""Call whichever provider is saved in settings."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai.config import load_config, require_ready
from app.services.ai.providers import build_provider


async def generate_json(
    session: AsyncSession,
    *,
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    require_enabled: bool,
) -> dict:
    config = await load_config(session)
    require_ready(config, require_enabled=require_enabled)
    provider = build_provider(config)
    return await provider.generate_json(system_prompt, user_prompt, schema)
