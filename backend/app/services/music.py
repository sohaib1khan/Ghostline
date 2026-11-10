"""Calm ambient playlist — five rotating tracks, editable by super admin."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_store import get_setting, set_setting

MUSIC_KEY = "ambient_music_playlist"

DEFAULT_TRACKS = [
    {
        "id": "dawn",
        "title": "Dawn",
        "url": "/sounds/music/calm-01-dawn.wav",
    },
    {
        "id": "harbor",
        "title": "Harbor",
        "url": "/sounds/music/calm-02-harbor.wav",
    },
    {
        "id": "mist",
        "title": "Mist",
        "url": "/sounds/music/calm-03-mist.wav",
    },
    {
        "id": "ember",
        "title": "Ember",
        "url": "/sounds/music/calm-04-ember.wav",
    },
    {
        "id": "tide",
        "title": "Tide",
        "url": "/sounds/music/calm-05-tide.wav",
    },
]


def _clean_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) > 500:
        raise ValueError("A track URL is too long")
    if text.startswith(("http://", "https://", "/")):
        return text
    raise ValueError("Track URLs must start with / or http(s)://")


def normalize_playlist(raw) -> dict:
    tracks_in = []
    if isinstance(raw, dict):
        tracks_in = list(raw.get("tracks") or [])
        enabled = bool(raw.get("enabled", True))
        rotate = bool(raw.get("rotate", True))
    else:
        enabled = True
        rotate = True
    tracks: list[dict] = []
    for index, default in enumerate(DEFAULT_TRACKS):
        raw_item = tracks_in[index] if index < len(tracks_in) else None
        item = raw_item if isinstance(raw_item, dict) else {}
        title = str(item.get("title") or default["title"]).strip()[:80]
        title = title or default["title"]
        url = _clean_url(item.get("url") or default["url"]) or default["url"]
        tracks.append(
            {
                "id": default["id"],
                "title": title,
                "url": url,
            }
        )
    return {"enabled": enabled, "rotate": rotate, "tracks": tracks}


async def get_playlist(session: AsyncSession) -> dict:
    stored = await get_setting(session, MUSIC_KEY)
    return normalize_playlist(stored)


async def save_playlist(session: AsyncSession, payload: dict) -> dict:
    cleaned = normalize_playlist(payload)
    await set_setting(session, MUSIC_KEY, cleaned)
    return cleaned
