"""Generic JSON webhook."""

from app.services.notifications import http
from app.services.notifications.base import Outbound


async def send(config: dict, message: Outbound) -> None:
    headers = {"Content-Type": "application/json"}
    token = (config.get("bearer_token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    await http.post_json(
        config["url"],
        headers=headers,
        json={
            "event": message.event,
            "title": message.title,
            "body": message.body,
            "recipient": message.recipient,
        },
    )
