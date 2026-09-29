"""Request rate limits. Storage is in-memory for the single backend process."""

from fastapi import Request
from slowapi import Limiter

from app.security.requests import client_ip


def rate_limit_key(request: Request) -> str:
    return client_ip(request) or "unknown"


limiter = Limiter(key_func=rate_limit_key, headers_enabled=False)
