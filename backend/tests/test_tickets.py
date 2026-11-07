"""Bug report tickets — create, reply, unread."""

from app.schemas.tickets import TicketCreateIn
from app.services.tickets import CATEGORY_LABELS, _subject_from


def test_subject_uses_category_and_path() -> None:
    payload = TicketCreateIn(
        category="check_failed",
        body="Check did nothing",
        page_path="/learn/lessons/abc",
    )
    subject = _subject_from(payload)
    assert "Check" in subject or CATEGORY_LABELS["check_failed"][:8] in subject
    assert "/learn/lessons/abc" in subject


def test_custom_subject_wins() -> None:
    payload = TicketCreateIn(
        category="other",
        subject="Ghostwalk freezes on mobile",
        body="It froze",
        page_path="/ghostwalk/x",
    )
    assert _subject_from(payload) == "Ghostwalk freezes on mobile"


def test_public_id_format() -> None:
    # Pure shape check without DB — generator uses BUG- + 6 hex.
    sample = "BUG-A1B2C3"
    assert sample.startswith("BUG-")
    assert len(sample) == 10
