"""ntfy provider. The server URL is required so events are not sent to a public default."""

from app.services.notifications import http
from app.services.notifications.base import Outbound


async def send(config: dict, message: Outbound) -> None:
    base = str(config["base_url"]).rstrip("/")
    headers = {"Title": message.title}
    token = (config.get("token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    await http.post_json(
        f"{base}/{config['topic']}",
        headers=headers,
        content=message.body.encode(),
    )
