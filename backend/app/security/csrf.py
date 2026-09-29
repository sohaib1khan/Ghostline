"""Double-submit CSRF. Mutating requests need the cookie and a matching header."""

import secrets

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings
from app.security.cookies import CSRF_COOKIE, CSRF_HEADER, csrf_cookie_kwargs
from app.security.tokens import new_token

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _matches(left: str, right: str) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return secrets.compare_digest(left, right)


def ensure_csrf_cookie(request: Request, response: Response) -> None:
    if CSRF_COOKIE in request.cookies:
        return
    response.set_cookie(CSRF_COOKIE, new_token(), **csrf_cookie_kwargs(get_settings()))


def _csrf_cookie_header(token: str) -> str:
    carrier = Response()
    carrier.set_cookie(CSRF_COOKIE, token, **csrf_cookie_kwargs(get_settings()))
    return carrier.headers["set-cookie"]


class CSRFMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        if request.method in UNSAFE_METHODS:
            cookie = request.cookies.get(CSRF_COOKIE, "")
            header = request.headers.get(CSRF_HEADER, "")
            if not _matches(cookie, header):
                response = JSONResponse(
                    {"detail": "CSRF token missing or invalid"},
                    status_code=403,
                )
                ensure_csrf_cookie(request, response)
                await response(scope, receive, send)
                return

        token = None if CSRF_COOKIE in request.cookies else new_token()

        async def send_with_cookie(message: Message) -> None:
            if token and message["type"] == "http.response.start":
                headers = MutableHeaders(raw=list(message["headers"]))
                headers.append("set-cookie", _csrf_cookie_header(token))
                message["headers"] = headers.raw
            await send(message)

        await self.app(scope, receive, send_with_cookie)
