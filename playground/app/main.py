"""Internal playground manager: create ephemeral workers, never expose Docker."""

from __future__ import annotations

import asyncio
import os
import secrets
import shlex
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app import docker_api
from app.mime_types import content_type_for
from app.packages import PackageError, install_packages
from app.templates import SEED_FILES

TOKEN = os.environ.get("PLAYGROUND_TOKEN", "").strip()
WORKER_IMAGE = os.environ.get("PLAYGROUND_WORKER_IMAGE", "ghostline-playground-worker:local")
MEMORY_MB = int(os.environ.get("PLAYGROUND_MEMORY_MB", "512"))
CPUS = float(os.environ.get("PLAYGROUND_CPUS", "0.5"))
WORKSPACE_MB = int(os.environ.get("PLAYGROUND_WORKSPACE_MB", "64"))
RUN_TIMEOUT = int(os.environ.get("PLAYGROUND_RUN_TIMEOUT", "8"))
# 12-hour session lifetime (extend resets another full window from now).
MAX_TTL_SECONDS = 12 * 60 * 60
SWEEP_INTERVAL_SECONDS = 60
RUN_ENV = [
    # Packages install under /tmp so they never clutter the workspace tree.
    "PYTHONPATH=/tmp/pg-vendor",
    "NODE_PATH=/tmp/pg-node_modules",
    # Discourage Flask/Werkzeug from starting a reloader server if someone calls app.run().
    "FLASK_DEBUG=0",
    "WERKZEUG_RUN_MAIN=true",
]

ALLOWED_BINARIES = {
    "python3": ["python3"],
    "python": ["python3"],
    "node": ["node"],
    "bash": ["bash"],
    "sh": ["sh"],
    "javac": ["javac"],
    "java": ["java"],
    "mcs": ["mcs"],
    "mono": ["mono"],
}

SESSIONS: dict[str, dict] = {}


class StartIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    ttl_seconds: int = Field(ge=60, le=MAX_TTL_SECONDS)


class PathIn(BaseModel):
    path: str = Field(min_length=1, max_length=200)


class WriteIn(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=200_000)


class RunIn(BaseModel):
    path: str | None = Field(default=None, max_length=200)
    argv: list[str] | None = Field(default=None, max_length=8)
    # One-shot shell line (ls, echo hi, …). Not a login TTY — just bash -c.
    shell: str | None = Field(default=None, max_length=500)


class TtlIn(BaseModel):
    ttl_seconds: int = Field(ge=60, le=MAX_TTL_SECONDS)


class PackagesIn(BaseModel):
    ecosystem: str = Field(min_length=3, max_length=8)
    packages: list[str] = Field(min_length=1, max_length=8)


def _auth(authorization: str | None) -> None:
    if not TOKEN:
        raise HTTPException(status_code=503, detail="Playground token is not configured")
    expected = f"Bearer {TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _session(session_id: str) -> dict:
    row = SESSIONS.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if row["expires_at"] <= datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Session expired")
    return row


async def _sweep() -> None:
    now = datetime.now(UTC)
    dead = [key for key, row in SESSIONS.items() if row["expires_at"] <= now]
    for key in dead:
        row = SESSIONS.pop(key, None)
        if row:
            await docker_api.destroy(row["container_id"])


async def _sweep_loop() -> None:
    """Destroy expired workers even when nobody hits the API."""
    while True:
        try:
            await _sweep()
        except Exception:
            pass
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sweeper = asyncio.create_task(_sweep_loop())
    try:
        yield
    finally:
        sweeper.cancel()
        try:
            await sweeper
        except asyncio.CancelledError:
            pass
        for key in list(SESSIONS):
            row = SESSIONS.pop(key)
            try:
                await docker_api.destroy(row["container_id"])
            except Exception:
                pass


app = FastAPI(title="Ghostline Playground Manager", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "docker": await docker_api.ping()}


@app.post("/v1/sessions")
async def start_session(
    body: StartIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    await _sweep()
    for row in SESSIONS.values():
        if row["user_id"] == body.user_id and row["expires_at"] > datetime.now(UTC):
            raise HTTPException(status_code=409, detail="User already has a playground session")
    short = secrets.token_hex(6)
    name = f"glpg-{short}"
    session_id = secrets.token_urlsafe(18)
    labels = {
        "ghostline.playground": "1",
        "ghostline.user": body.user_id[:80],
        "ghostline.session": session_id[:40],
    }
    try:
        container_id = await docker_api.create_and_start(
            name=name,
            image=WORKER_IMAGE,
            memory_mb=MEMORY_MB,
            cpus=CPUS,
            workspace_mb=WORKSPACE_MB,
            labels=labels,
        )
    except docker_api.DockerError as exc:
        raise HTTPException(status_code=502, detail=exc.detail) from exc
    expires = datetime.now(UTC) + timedelta(seconds=body.ttl_seconds)
    try:
        for rel_path, content in SEED_FILES.items():
            await docker_api.write_file(container_id, rel_path, content)
    except docker_api.DockerError:
        await docker_api.destroy(container_id)
        raise HTTPException(status_code=502, detail="Could not seed the workspace") from None
    SESSIONS[session_id] = {
        "user_id": body.user_id,
        "container_id": container_id,
        "name": name,
        "expires_at": expires,
        "ttl_seconds": body.ttl_seconds,
    }
    return {
        "session_id": session_id,
        "expires_at": expires.isoformat(),
        "ttl_seconds": body.ttl_seconds,
        "remaining_seconds": body.ttl_seconds,
        "memory_mb": MEMORY_MB,
    }


@app.get("/v1/sessions/{session_id}")
async def get_session(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    await _sweep()
    row = _session(session_id)
    return {
        "session_id": session_id,
        "expires_at": row["expires_at"].isoformat(),
        "ttl_seconds": row["ttl_seconds"],
        "memory_mb": MEMORY_MB,
        "remaining_seconds": max(0, int((row["expires_at"] - datetime.now(UTC)).total_seconds())),
    }


@app.patch("/v1/sessions/{session_id}/ttl")
async def set_ttl(
    session_id: str,
    body: TtlIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    row = _session(session_id)
    row["ttl_seconds"] = body.ttl_seconds
    row["expires_at"] = datetime.now(UTC) + timedelta(seconds=body.ttl_seconds)
    return {
        "session_id": session_id,
        "expires_at": row["expires_at"].isoformat(),
        "ttl_seconds": row["ttl_seconds"],
        "remaining_seconds": body.ttl_seconds,
    }


@app.delete("/v1/sessions/{session_id}")
async def stop_session(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    row = SESSIONS.pop(session_id, None)
    if row:
        await docker_api.destroy(row["container_id"])
    return {"stopped": True}


@app.get("/v1/sessions/{session_id}/fs/tree")
async def tree(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    row = _session(session_id)
    try:
        entries = await docker_api.list_tree(row["container_id"])
    except docker_api.DockerError as exc:
        raise HTTPException(
            status_code=exc.status if exc.status < 500 else 502, detail=exc.detail
        ) from exc
    return {"entries": entries}


@app.get("/v1/sessions/{session_id}/fs/file")
async def read_file(
    session_id: str,
    path: str,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    row = _session(session_id)
    try:
        content = await docker_api.read_file(row["container_id"], path)
    except docker_api.DockerError as exc:
        raise HTTPException(
            status_code=exc.status if exc.status < 500 else 502, detail=exc.detail
        ) from exc
    return {"path": path, "content": content}


@app.put("/v1/sessions/{session_id}/fs/file")
async def write_file(
    session_id: str,
    body: WriteIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    row = _session(session_id)
    try:
        await docker_api.write_file(row["container_id"], body.path, body.content)
    except docker_api.DockerError as exc:
        raise HTTPException(
            status_code=exc.status if 400 <= exc.status < 500 else 502, detail=exc.detail
        ) from exc
    return {"path": body.path, "saved": True}


@app.post("/v1/sessions/{session_id}/fs/mkdir")
async def make_dir(
    session_id: str,
    body: PathIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    row = _session(session_id)
    try:
        await docker_api.mkdir(row["container_id"], body.path)
    except docker_api.DockerError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    return {"path": body.path, "created": True}


@app.delete("/v1/sessions/{session_id}/fs/path")
async def remove_path(
    session_id: str,
    path: str,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    row = _session(session_id)
    try:
        await docker_api.delete_path(row["container_id"], path)
    except docker_api.DockerError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    return {"path": path, "deleted": True}


@app.get("/v1/sessions/{session_id}/preview/{path:path}")
async def preview_file(
    session_id: str,
    path: str,
    authorization: str | None = Header(default=None),
) -> Response:
    """Serve a workspace file for the in-app browser. No worker ports."""
    _auth(authorization)
    row = _session(session_id)
    try:
        data = await docker_api.read_bytes(row["container_id"], path)
    except docker_api.DockerError as exc:
        raise HTTPException(
            status_code=exc.status if 400 <= exc.status < 500 else 502,
            detail=exc.detail,
        ) from exc
    ctype = content_type_for(path)
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if ctype.startswith("text/html"):
        # Block network from preview pages (connect-src none). Assets still load
        # via this same preview path ('self'). frame-ancestors self allows the
        # Ghostline Browser tab iframe.
        headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "connect-src 'none'; "
            "form-action 'none'; "
            "frame-src 'none'; "
            "object-src 'none'; "
            "base-uri 'none'; "
            "frame-ancestors 'self'"
        )
    return Response(content=data, media_type=ctype, headers=headers)


@app.post("/v1/sessions/{session_id}/packages")
async def packages(
    session_id: str,
    body: PackagesIn,
    authorization: str | None = Header(default=None),
) -> dict:
    """Download on the manager; install offline inside the air-gapped worker."""
    _auth(authorization)
    row = _session(session_id)
    try:
        return await install_packages(
            row["container_id"],
            ecosystem=body.ecosystem,
            packages=body.packages,
        )
    except PackageError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    except docker_api.DockerError as exc:
        raise HTTPException(status_code=502, detail=exc.detail) from exc


@app.post("/v1/sessions/{session_id}/run")
async def run_cmd(
    session_id: str,
    body: RunIn,
    authorization: str | None = Header(default=None),
) -> dict:
    _auth(authorization)
    row = _session(session_id)
    argv = _resolve_argv(body)
    # Hard wall: GNU timeout kills servers (app.run, etc.) so ports are freed.
    timed = ["timeout", "--kill-after=2s", f"{RUN_TIMEOUT}s", *argv]
    try:
        # Reap leftovers from earlier timed-out runs that still hold ports.
        await docker_api.reap_stray_processes(row["container_id"])
        result = await docker_api.exec_run(
            row["container_id"],
            timed,
            timeout_seconds=RUN_TIMEOUT + 4,
            env=RUN_ENV,
        )
    except docker_api.DockerError as exc:
        raise HTTPException(status_code=502, detail=exc.detail) from exc
    except httpx.TimeoutException:
        await docker_api.reap_stray_processes(row["container_id"])
        raise HTTPException(status_code=408, detail="Run timed out") from None
    output = result["output"]
    if result["exit_code"] == 124:
        output = (
            (output or "")
            + "\n(run timed out — long-running servers like app.run() are not supported; "
            "use Flask's test_client() instead)"
        ).lstrip()
    return {
        "argv": argv,
        "exit_code": result["exit_code"],
        "output": output,
        "timeout_seconds": RUN_TIMEOUT,
    }


def _resolve_argv(body: RunIn) -> list[str]:
    modes = sum(1 for item in (body.shell, body.argv, body.path) if item)
    if modes > 1:
        raise HTTPException(status_code=400, detail="Choose one of shell, argv, or path")
    if body.shell is not None:
        command = body.shell.strip()
        if not command:
            raise HTTPException(status_code=400, detail="Enter a command")
        if "\x00" in command:
            raise HTTPException(status_code=400, detail="Invalid command")
        # DECISION: bash -c keeps pipes/flags inside the isolated worker. There is
        # no interactive TTY; each submit is one timed exec.
        return ["bash", "-c", command]
    if body.argv:
        if not body.argv or len(body.argv) > 8:
            raise HTTPException(status_code=400, detail="Invalid command")
        binary = body.argv[0]
        if binary not in ALLOWED_BINARIES:
            raise HTTPException(status_code=400, detail="That program is not allowed")
        mapped = ALLOWED_BINARIES[binary][:]
        for part in body.argv[1:]:
            if not isinstance(part, str) or len(part) > 200:
                raise HTTPException(status_code=400, detail="Invalid argument")
            if part.startswith("-"):
                raise HTTPException(status_code=400, detail="Flags are not allowed")
            if part.startswith("/") or ".." in part:
                raise HTTPException(status_code=400, detail="Absolute paths are not allowed")
            mapped.append(part)
        return mapped
    if not body.path:
        raise HTTPException(status_code=400, detail="Choose a file to run")
    try:
        safe = docker_api._safe_rel(body.path)
    except docker_api.DockerError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    lower = safe.lower()
    if lower.endswith(".py"):
        return ["python3", safe]
    if lower.endswith(".js") or lower.endswith(".mjs"):
        return ["node", safe]
    if lower.endswith(".sh") or lower.endswith(".bash"):
        return ["bash", safe]
    if lower.endswith(".java"):
        # Compile then run the public class matching the file stem.
        path = PurePosixPath(safe)
        parent = "." if str(path.parent) in {"", "."} else str(path.parent)
        stem = path.stem
        cmd = (
            f"javac {shlex.quote(safe)} && "
            f"java -cp {shlex.quote(parent)} {shlex.quote(stem)}"
        )
        return ["bash", "-c", cmd]
    if lower.endswith(".cs"):
        cmd = (
            f"mcs -out:/tmp/pg-out.exe {shlex.quote(safe)} && "
            f"mono /tmp/pg-out.exe"
        )
        return ["bash", "-c", cmd]
    raise HTTPException(status_code=400, detail="Run .py, .js, .sh, .java, or .cs files")
