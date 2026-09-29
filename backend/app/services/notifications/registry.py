"""Provider lookup."""

from app.services.notifications import discord, gotify, ntfy, resend, slack, smtp, webhook
from app.services.notifications.base import Provider

SENDERS: dict[str, Provider] = {
    "resend": resend.send,
    "smtp": smtp.send,
    "gotify": gotify.send,
    "slack": slack.send,
    "discord": discord.send,
    "ntfy": ntfy.send,
    "webhook": webhook.send,
}
