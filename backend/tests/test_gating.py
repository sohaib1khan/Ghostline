"""Mastery gating pure functions."""

from app.services.gating import lesson_progress_label, pick_boss_exercises, unlock_needed


def test_unlock_needed_eighty_percent() -> None:
    stats = unlock_needed(10, 8)
    assert stats["ready"] is True
    assert stats["needed"] == 0
    assert unlock_needed(10, 7)["ready"] is False
    assert unlock_needed(10, 7)["needed"] == 1


def test_lesson_done_requires_recall() -> None:
    assert (
        lesson_progress_label([("trace", "completed"), ("fill", "completed"), ("recall", None)])
        == "practiced"
    )
    assert (
        lesson_progress_label(
            [("trace", "completed"), ("fill", "completed"), ("recall", "completed")]
        )
        == "done"
    )
    assert lesson_progress_label([("trace", None), ("recall", None)]) == "new"
    assert lesson_progress_label([("recall", "started")]) == "started"


def test_pick_boss_prefers_recalls() -> None:
    class Fake:
        def __init__(self, type_: str) -> None:
            self.type = type_

    items = [Fake("recall") for _ in range(3)] + [Fake("challenge") for _ in range(4)]
    picked = pick_boss_exercises(items, limit=8)
    assert len(picked) >= 5
    assert all(item.type in {"recall", "challenge"} for item in picked)
