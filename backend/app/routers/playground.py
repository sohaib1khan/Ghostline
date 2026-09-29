"""Signed-in playground: ephemeral worker IDE (no persisted files)."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.user import User
from app.security.deps import current_user
from app.security.rate_limit import limiter
from app.services import playground as pg

router = APIRouter(prefix="/playground", tags=["playground"])


class StartIn(BaseModel):
    ttl_minutes: int | None = Field(default=None, ge=1, le=120)


class TtlIn(BaseModel):
    ttl_minutes: int = Field(ge=1, le=120)


class WriteIn(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=200_000)


class PathIn(BaseModel):
    path: str = Field(min_length=1, max_length=200)


class RunIn(BaseModel):
    path: str | None = Field(default=None, max_length=200)
    argv: list[str] | None = Field(default=None, max_length=8)
    shell: str | None = Field(default=None, max_length=500)


@router.get("/status")
async def status(user: User = Depends(current_user)) -> dict:
    del user
    limits = pg.playground_limits()
    return limits


@router.get("/session")
async def session(user: User = Depends(current_user)) -> dict:
    try:
        current = await pg.session_for_user(user.id)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)
    return {"session": current, **pg.playground_limits()}


@router.post("/start")
@limiter.limit("6/minute")
async def start(
    request: Request,
    body: StartIn,
    user: User = Depends(current_user),
) -> dict:
    del request
    settings = get_settings()
    minutes = body.ttl_minutes if body.ttl_minutes is not None else settings.playground_ttl_default_minutes
    try:
        return await pg.start_for_user(user.id, minutes)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)


@router.patch("/session/ttl")
@limiter.limit("20/minute")
async def update_ttl(
    request: Request,
    body: TtlIn,
    user: User = Depends(current_user),
) -> dict:
    del request
    try:
        return await pg.set_ttl_for_user(user.id, body.ttl_minutes)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)


@router.post("/stop")
@limiter.limit("20/minute")
async def stop(
    request: Request,
    user: User = Depends(current_user),
) -> dict:
    del request
    try:
        return await pg.stop_for_user(user.id)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)


@router.get("/fs/tree")
async def tree(user: User = Depends(current_user)) -> dict:
    try:
        return await pg.tree(user.id)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)


@router.get("/fs/file")
async def read_file(path: str, user: User = Depends(current_user)) -> dict:
    try:
        return await pg.read_file(user.id, path)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)


@router.put("/fs/file")
@limiter.limit("60/minute")
async def write_file(
    request: Request,
    body: WriteIn,
    user: User = Depends(current_user),
) -> dict:
    del request
    try:
        return await pg.write_file(user.id, body.path, body.content)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)


@router.post("/fs/mkdir")
@limiter.limit("30/minute")
async def mkdir(
    request: Request,
    body: PathIn,
    user: User = Depends(current_user),
) -> dict:
    del request
    try:
        return await pg.mkdir(user.id, body.path)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)


@router.delete("/fs/path")
@limiter.limit("30/minute")
async def delete_path(
    request: Request,
    path: str,
    user: User = Depends(current_user),
) -> dict:
    del request
    try:
        return await pg.delete_path(user.id, path)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)


@router.post("/run")
@limiter.limit("30/minute")
async def run(
    request: Request,
    body: RunIn,
    user: User = Depends(current_user),
) -> dict:
    del request
    try:
        return await pg.run(user.id, path=body.path, argv=body.argv, shell=body.shell)
    except pg.PlaygroundError as exc:
        pg.raise_http(exc)
