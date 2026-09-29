"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.routers.admin.ai import router as admin_ai_router
from app.routers.admin.content import router as admin_content_router
from app.routers.admin.notifications import router as admin_notifications_router
from app.routers.admin.settings import router as admin_settings_router
from app.routers.admin.users import router as admin_users_router
from app.routers.auth import router as auth_router
from app.routers.check import router as check_router
from app.routers.demo import router as demo_router
from app.routers.games import router as games_router
from app.routers.health import router as health_router
from app.routers.learn import router as learn_router
from app.routers.me import router as me_router
from app.routers.playground import router as playground_router
from app.routers.setup import router as setup_router
from app.security.csrf import CSRFMiddleware
from app.security.rate_limit import limiter
from app.startup import shutdown, startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    yield
    await shutdown()


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # DECISION: the response does not repeat the limit rule.
    del request, exc
    return JSONResponse({"detail": "Too many requests. Try again soon."}, status_code=429)


def create_app() -> FastAPI:
    settings = get_settings()
    # DECISION: interactive API docs stay on in development and are removed in
    # production so the public surface is only the routes we intend to serve.
    docs_enabled = settings.app_env != "production"
    app = FastAPI(
        title="Ghostline",
        version="1.0.0",
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(CSRFMiddleware)
    app.include_router(health_router, prefix="/api")
    app.include_router(setup_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(me_router, prefix="/api")
    app.include_router(learn_router, prefix="/api")
    app.include_router(check_router, prefix="/api")
    app.include_router(demo_router, prefix="/api")
    app.include_router(games_router, prefix="/api")
    app.include_router(playground_router, prefix="/api")
    app.include_router(admin_ai_router, prefix="/api")
    app.include_router(admin_users_router, prefix="/api")
    app.include_router(admin_notifications_router, prefix="/api")
    app.include_router(admin_content_router, prefix="/api")
    app.include_router(admin_settings_router, prefix="/api")
    return app


app = create_app()
