"""Gotify provider. The app token is sent as a header, not a query parameter."""

from app.services.notifications import http
from app.services.notifications.base import Outbound


async def send(config: dict, message: Outbound) -> None:
    base = str(config["base_url"]).rstrip("/")
    await http.post_json(
        f"{base}/message",
        headers={"X-Gotify-Key": config["token"]},
        json={
            "title": message.title,
            "message": message.body,
            "priority": int(config.get("priority") or 5),
        },
    )
