"""Dashboard continue target prefers the learner's most recent track."""

from app.services.progress import _pick_continue


def test_pick_continue_prefers_recent_activity_over_catalog_order() -> None:
    tracks = [
        {
            "slug": "bash",
            "name": "Bash",
            "continue_lesson_id": "bash-lesson",
            "continue_lesson_title": "Chain commands",
            "last_activity_at": "2024-01-01T00:00:00+00:00",
        },
        {
            "slug": "csharp",
            "name": "C#",
            "continue_lesson_id": "csharp-lesson",
            "continue_lesson_title": "Print hello",
            "last_activity_at": "2024-06-01T12:00:00+00:00",
        },
        {
            "slug": "java",
            "name": "Java",
            "continue_lesson_id": "java-lesson",
            "continue_lesson_title": "Print hello",
            "last_activity_at": None,
        },
    ]
    chosen = _pick_continue(tracks)
    assert chosen is not None
    assert chosen["track_slug"] == "csharp"
    assert chosen["lesson_id"] == "csharp-lesson"
    assert chosen["lesson_title"] == "Print hello"


def test_pick_continue_falls_back_to_first_incomplete_without_activity() -> None:
    tracks = [
        {
            "slug": "bash",
            "name": "Bash",
            "continue_lesson_id": "bash-lesson",
            "continue_lesson_title": "Chain commands",
            "last_activity_at": None,
        },
        {
            "slug": "python",
            "name": "Python",
            "continue_lesson_id": "py-lesson",
            "continue_lesson_title": "Print",
            "last_activity_at": None,
        },
    ]
    chosen = _pick_continue(tracks)
    assert chosen is not None
    assert chosen["track_slug"] == "bash"


def test_pick_continue_skips_finished_tracks() -> None:
    tracks = [
        {
            "slug": "bash",
            "name": "Bash",
            "continue_lesson_id": None,
            "continue_lesson_title": None,
            "last_activity_at": "2024-06-01T12:00:00+00:00",
        },
        {
            "slug": "java",
            "name": "Java",
            "continue_lesson_id": "java-lesson",
            "continue_lesson_title": "A loop",
            "last_activity_at": "2024-05-01T00:00:00+00:00",
        },
    ]
    chosen = _pick_continue(tracks)
    assert chosen is not None
    assert chosen["track_slug"] == "java"
