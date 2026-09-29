"""Starter tracks. Lessons load from backend/app/seed/lessons."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, UserTrackAccess
from app.models.user import User

# Keep these slugs stable. Lessons and permissions refer to them.
STARTER_TRACKS = (
    {
        "slug": "bash",
        "name": "Bash",
        "description": "Learn the shell from basics to small scripts.",
        "icon": "terminal",
        "color": "#8fb9a8",
        "order": 1,
    },
    {
        "slug": "python",
        "name": "Python",
        "description": "Learn Python from first lines to small programs.",
        "icon": "snake",
        "color": "#a3b8d4",
        "order": 2,
    },
    {
        "slug": "go",
        "name": "Go",
        "description": "Learn Go from a tiny program to real flow.",
        "icon": "gopher",
        "color": "#9ccc9c",
        "order": 3,
    },
    {
        "slug": "javascript",
        "name": "JavaScript",
        "description": "Learn JavaScript from the page to small scripts.",
        "icon": "braces",
        "color": "#d4c4a8",
        "order": 4,
    },
    {
        "slug": "sql",
        "name": "SQL",
        "description": "Learn SQL from simple selects to richer queries.",
        "icon": "table",
        "color": "#c4b4d4",
        "order": 5,
    },
)


async def ensure_tracks(session: AsyncSession) -> None:
    rows = [
        {
            "id": uuid.uuid4(),
            "slug": item["slug"],
            "name": item["name"],
            "description": item["description"],
            "icon": item["icon"],
            "color": item["color"],
            "position": item["order"],
            "is_active": True,
        }
        for item in STARTER_TRACKS
    ]
    await session.execute(
        insert(Track).values(rows).on_conflict_do_nothing(index_elements=["slug"])
    )
    # Refresh descriptions for existing starter tracks so the learn path copy stays current.
    by_slug = {item["slug"]: item for item in STARTER_TRACKS}
    existing = list((await session.scalars(select(Track))).all())
    for track in existing:
        wanted = by_slug.get(track.slug)
        if wanted and track.description != wanted["description"]:
            track.description = wanted["description"]
    await session.commit()


async def list_visible_tracks(session: AsyncSession, user: User) -> list[Track]:
    stmt = select(Track).where(Track.is_active.is_(True)).order_by(Track.position, Track.slug)
    if user.role != "admin":
        stmt = stmt.join(UserTrackAccess, UserTrackAccess.track_id == Track.id).where(
            UserTrackAccess.user_id == user.id
        )
    return list((await session.scalars(stmt)).all())
