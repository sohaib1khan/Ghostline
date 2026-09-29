"""Resend email provider."""

from app.services.notifications import http
from app.services.notifications.base import Outbound


async def send(config: dict, message: Outbound) -> None:
    await http.post_json(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {config['api_key']}"},
        json={
            "from": config["from_email"],
            "to": [message.recipient],
            "subject": message.title,
            "text": message.body,
        },
    )
