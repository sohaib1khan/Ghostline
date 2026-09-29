"""Cookie names and flags for the session and the CSRF token."""

from app.config import Settings

SESSION_COOKIE = "ghostline_session"
CSRF_COOKIE = "ghostline_csrf"
CSRF_HEADER = "X-CSRF-Token"


def cookies_are_secure(settings: Settings) -> bool:
    # DECISION: the Secure flag is on only in production. Local Compose is HTTP,
    # and a Secure cookie would be dropped by the browser.
    return settings.app_env == "production"


def session_cookie_kwargs(settings: Settings) -> dict:
    return {
        "httponly": True,
        "secure": cookies_are_secure(settings),
        "samesite": "lax",
        "path": "/",
        "max_age": settings.session_ttl_hours * 3600,
    }


def csrf_cookie_kwargs(settings: Settings) -> dict:
    # The frontend must read this cookie and send it back as a header.
    return {
        "httponly": False,
        "secure": cookies_are_secure(settings),
        "samesite": "lax",
        "path": "/",
        "max_age": settings.session_ttl_hours * 3600,
    }
