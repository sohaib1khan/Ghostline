"""HTTP POST for AI providers. Redirects are not followed."""

import httpx

from app.services.ai.errors import AiError

# A lesson draft is JSON, not a file. Stop a hostile endpoint from streaming
# an unbounded body into the process.
MAX_RESPONSE_BYTES = 1_000_000


async def post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict,
    timeout: float,
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise AiError("The AI provider timed out.", status_code=502) from exc
    except httpx.HTTPError as exc:
        raise AiError("Could not reach the AI provider.", status_code=502) from exc
    # DECISION: a redirect is rejected so an API key in the request header
    # cannot be forwarded to a different host.
    if response.is_redirect:
        raise AiError(
            "The AI provider returned a redirect, which Ghostline does not follow.",
            status_code=502,
        )
    if response.status_code in {401, 403}:
        raise AiError("The AI provider rejected the API key.", status_code=502)
    if response.status_code >= 400:
        raise AiError(
            f"The AI provider returned HTTP {response.status_code}.",
            status_code=502,
        )
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise AiError("The AI provider response was too large.", status_code=502)
    try:
        body = response.json()
    except ValueError as exc:
        raise AiError("The AI provider did not return JSON.", status_code=502) from exc
    if not isinstance(body, dict):
        raise AiError("The AI provider did not return a JSON object.", status_code=502)
    return body
