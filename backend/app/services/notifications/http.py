"""HTTP POST helper. Redirects are not followed."""

import httpx

from app.services.notifications.base import DeliveryError

# DECISION: follow_redirects stays off so a channel cannot bounce the request
# (and any Authorization header) to a different host.
DEFAULT_TIMEOUT = 10.0


async def post_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict | None = None,
    content: bytes | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(url, headers=headers, json=json, content=content)
    except httpx.HTTPError as exc:
        raise DeliveryError("Could not reach the notification service") from exc
    if response.status_code >= 400:
        raise DeliveryError(f"The service returned HTTP {response.status_code}")
