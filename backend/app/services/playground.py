"""Authenticated backend client for the internal playground manager."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import get_settings

# Fixed product lifetime — one full workday window, extend resets another.
PLAYGROUND_SESSION_MINUTES = 720

# user_id -> session_id (process-local; one backend replica)
USER_SESSIONS: dict[str, str] = {}


class PlaygroundError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def playground_limits() -> dict[str, Any]:
    settings = get_settings()
    return {
        # Always advertise available; start still needs PLAYGROUND_TOKEN + manager.
        "enabled": True,
        "ttl_min_minutes": PLAYGROUND_SESSION_MINUTES,
        "ttl_max_minutes": PLAYGROUND_SESSION_MINUTES,
        "ttl_default_minutes": PLAYGROUND_SESSION_MINUTES,
        "memory_mb": settings.playground_memory_mb,
        "run_timeout_seconds": settings.playground_run_timeout_seconds,
        "one_session_per_user": True,
        "preview": True,
        "packages": True,
    }


def clamp_ttl_minutes(minutes: int) -> int:
    del minutes
    return PLAYGROUND_SESSION_MINUTES


async def _request(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
    timeout: float = 30.0,
) -> Any:
    settings = get_settings()
    if not settings.playground_token:
        raise PlaygroundError(503, "Playground is not configured")
    headers = {"Authorization": f"Bearer {settings.playground_token}"}
    url = f"{settings.playground_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method, url, headers=headers, json=json, params=params
            )
    except httpx.HTTPError as exc:
        raise PlaygroundError(503, "Playground manager is unreachable") from exc
    if response.status_code >= 400:
        detail = "Playground request failed"
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("detail"):
                detail = str(payload["detail"])
        except ValueError:
            detail = response.text[:200] or detail
        raise PlaygroundError(response.status_code, detail)
    if response.status_code == 204 or not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise PlaygroundError(502, "Playground manager returned invalid data") from exc


def raise_http(exc: PlaygroundError) -> None:
    raise HTTPException(status_code=min(exc.status, 503), detail=exc.detail) from exc


async def start_for_user(user_id: uuid.UUID, ttl_minutes: int) -> dict:
    minutes = clamp_ttl_minutes(ttl_minutes)
    key = str(user_id)
    existing = USER_SESSIONS.get(key)
    if existing:
        try:
            current = await _request("GET", f"/v1/sessions/{existing}")
            return {**current, "session_id": existing, "resumed": True}
        except PlaygroundError:
            USER_SESSIONS.pop(key, None)
    # Container create can take longer than a normal FS call.
    body = await _request(
        "POST",
        "/v1/sessions",
        json={"user_id": key, "ttl_seconds": minutes * 60},
        timeout=90.0,
    )
    USER_SESSIONS[key] = body["session_id"]
    return {
        **body,
        "resumed": False,
        "ttl_min_minutes": PLAYGROUND_SESSION_MINUTES,
        "ttl_max_minutes": PLAYGROUND_SESSION_MINUTES,
    }


async def session_for_user(user_id: uuid.UUID) -> dict | None:
    key = str(user_id)
    session_id = USER_SESSIONS.get(key)
    if not session_id:
        return None
    try:
        body = await _request("GET", f"/v1/sessions/{session_id}", timeout=5.0)
    except PlaygroundError as exc:
        # Missing/expired workers and brief manager blips should not brick the page.
        # Clear the mapping so Start can create a fresh session.
        if exc.status in {404, 410, 502, 503, 504}:
            USER_SESSIONS.pop(key, None)
            return None
        raise
    return {**body, "session_id": session_id}


async def manager_reachable() -> bool:
    try:
        await _request("GET", "/health", timeout=3.0)
        return True
    except PlaygroundError:
        return False


async def stop_for_user(user_id: uuid.UUID) -> dict:
    key = str(user_id)
    session_id = USER_SESSIONS.pop(key, None)
    if not session_id:
        return {"stopped": True}
    try:
        await _request("DELETE", f"/v1/sessions/{session_id}")
    except PlaygroundError as exc:
        if exc.status not in {404, 410}:
            raise
    return {"stopped": True}


async def set_ttl_for_user(user_id: uuid.UUID, ttl_minutes: int) -> dict:
    key = str(user_id)
    session_id = USER_SESSIONS.get(key)
    if not session_id:
        raise PlaygroundError(404, "No active playground session")
    minutes = clamp_ttl_minutes(ttl_minutes)
    body = await _request(
        "PATCH",
        f"/v1/sessions/{session_id}/ttl",
        json={"ttl_seconds": minutes * 60},
    )
    return {**body, "session_id": session_id}


def require_session_id(user_id: uuid.UUID) -> str:
    session_id = USER_SESSIONS.get(str(user_id))
    if not session_id:
        raise PlaygroundError(404, "No active playground session")
    return session_id


async def tree(user_id: uuid.UUID) -> dict:
    session_id = require_session_id(user_id)
    return await _request("GET", f"/v1/sessions/{session_id}/fs/tree")


async def read_file(user_id: uuid.UUID, path: str) -> dict:
    session_id = require_session_id(user_id)
    return await _request(
        "GET", f"/v1/sessions/{session_id}/fs/file", params={"path": path}
    )


async def write_file(user_id: uuid.UUID, path: str, content: str) -> dict:
    session_id = require_session_id(user_id)
    return await _request(
        "PUT",
        f"/v1/sessions/{session_id}/fs/file",
        json={"path": path, "content": content},
    )


async def mkdir(user_id: uuid.UUID, path: str) -> dict:
    session_id = require_session_id(user_id)
    return await _request(
        "POST",
        f"/v1/sessions/{session_id}/fs/mkdir",
        json={"path": path},
    )


async def delete_path(user_id: uuid.UUID, path: str) -> dict:
    session_id = require_session_id(user_id)
    return await _request(
        "DELETE",
        f"/v1/sessions/{session_id}/fs/path",
        params={"path": path},
    )


async def preview_bytes(user_id: uuid.UUID, path: str) -> tuple[bytes, str]:
    settings = get_settings()
    if not settings.playground_token:
        raise PlaygroundError(503, "Playground is not configured")
    session_id = require_session_id(user_id)
    headers = {"Authorization": f"Bearer {settings.playground_token}"}
    url = f"{settings.playground_url.rstrip('/')}/v1/sessions/{session_id}/preview/{path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise PlaygroundError(503, "Playground manager is unreachable") from exc
    if response.status_code >= 400:
        detail = "Playground request failed"
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("detail"):
                detail = str(payload["detail"])
        except ValueError:
            detail = response.text[:200] or detail
        raise PlaygroundError(response.status_code, detail)
    ctype = response.headers.get("content-type") or "application/octet-stream"
    return response.content, ctype


async def install_packages(
    user_id: uuid.UUID, *, ecosystem: str, packages: list[str]
) -> dict:
    session_id = require_session_id(user_id)
    return await _request(
        "POST",
        f"/v1/sessions/{session_id}/packages",
        json={"ecosystem": ecosystem, "packages": packages},
        timeout=120.0,
    )


async def run(
    user_id: uuid.UUID,
    *,
    path: str | None = None,
    argv: list[str] | None = None,
    shell: str | None = None,
) -> dict:
    session_id = require_session_id(user_id)
    payload: dict[str, Any] = {}
    if path:
        payload["path"] = path
    if argv:
        payload["argv"] = argv
    if shell is not None:
        payload["shell"] = shell
    return await _request("POST", f"/v1/sessions/{session_id}/run", json=payload)
