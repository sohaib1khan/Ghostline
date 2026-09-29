"""SMTP email provider. The network call runs off the event loop."""

import asyncio
import smtplib
from email.message import EmailMessage

from app.services.notifications.base import DeliveryError, Outbound


def _deliver(config: dict, message: Outbound) -> None:
    security = config["security"]
    host = config["host"]
    port = int(config["port"])
    if security == "ssl":
        client = smtplib.SMTP_SSL(host, port, timeout=10)
    else:
        client = smtplib.SMTP(host, port, timeout=10)
    try:
        client.ehlo()
        if security == "starttls":
            client.starttls()
            client.ehlo()
        username = (config.get("username") or "").strip()
        password = config.get("password") or ""
        if username:
            client.login(username, password)
        email = EmailMessage()
        email["From"] = config["from_email"]
        email["To"] = message.recipient or ""
        email["Subject"] = message.title
        email.set_content(message.body)
        client.send_message(email)
    except (OSError, smtplib.SMTPException) as exc:
        raise DeliveryError("SMTP delivery failed") from exc
    finally:
        try:
            client.quit()
        except (OSError, smtplib.SMTPException):
            pass


async def send(config: dict, message: Outbound) -> None:
    if not message.recipient:
        raise DeliveryError("No recipient address")
    await asyncio.to_thread(_deliver, config, message)
