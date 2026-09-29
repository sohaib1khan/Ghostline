"""Client address and user agent, truncated before they are stored."""


def client_ip(request) -> str | None:
    # DECISION: Nginx appends the real peer, so the last X-Forwarded-For
    # address is the one we keep. The backend port is not published.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[-1].strip()
    elif request.client and request.client.host:
        ip = request.client.host
    else:
        return None
    return ip[:64] or None


def client_user_agent(request) -> str | None:
    agent = request.headers.get("user-agent", "").strip()
    if not agent:
        return None
    return agent[:300]
