"""Plain-text notices. Nothing here includes a secret or a session token."""

from app.config import get_settings
from app.services.notifications.base import Outbound
from app.services.notifications.fields import EMAIL_PROVIDERS, USER_EMAIL_EVENTS


def recipient_for(provider: str, event: str, config: dict, payload: dict) -> str | None:
    if provider not in EMAIL_PROVIDERS:
        return None
    if event in USER_EMAIL_EVENTS:
        email = payload.get("email")
        return email if isinstance(email, str) else None
    to_email = config.get("to_email")
    return to_email if isinstance(to_email, str) and to_email else None


def build_message(event: str, payload: dict, *, recipient: str | None) -> Outbound:
    base = get_settings().app_base_url
    first = str(payload.get("first_name") or "").strip()
    last = str(payload.get("last_name") or "").strip()
    email = str(payload.get("email") or "").strip()
    who = " ".join(part for part in (first, last) if part)
    if event == "user.signup":
        title = "New Ghostline signup"
        body = f"{who} ({email}) asked for access."
    elif event == "user.approved":
        title = "Your Ghostline access was approved"
        body = f"You can sign in at {base}/login."
    elif event == "user.rejected":
        title = "Your Ghostline request was not approved"
        body = "An admin reviewed your request. Contact them if you think that is a mistake."
    elif event == "admin.login":
        title = "Ghostline admin sign-in"
        # DECISION: the notice names the account and leaves out the IP and session.
        body = f"{email} signed in."
    elif event == "notification.test":
        title = "Ghostline test"
        body = "This is a test message from Ghostline."
    elif event == "content.published":
        title = "Ghostline lesson published"
        lesson_title = str(payload.get("title") or "A lesson")
        track = str(payload.get("track") or "")
        body = f"{lesson_title} is now published"
        if track:
            body = f"{body} in {track}"
        body = f"{body}."
    else:
        title = "Ghostline"
        body = event
    return Outbound(event=event, title=title, body=body, recipient=recipient)
