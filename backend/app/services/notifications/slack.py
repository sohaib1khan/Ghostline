"""Slack incoming webhook."""

from app.services.notifications import http
from app.services.notifications.base import Outbound


async def send(config: dict, message: Outbound) -> None:
    await http.post_json(
        config["webhook_url"],
        json={"text": f"*{message.title}*\n{message.body}"},
    )
