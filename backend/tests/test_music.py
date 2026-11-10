"""Ambient playlist normalization."""

from app.services.music import DEFAULT_TRACKS, normalize_playlist


def test_playlist_always_has_five_tracks() -> None:
    body = normalize_playlist({"enabled": True, "tracks": [{"title": "Only one", "url": "/a.wav"}]})
    assert body["enabled"] is True
    assert len(body["tracks"]) == 5
    assert body["tracks"][0]["title"] == "Only one"
    assert body["tracks"][0]["url"] == "/a.wav"
    assert body["tracks"][1]["url"] == DEFAULT_TRACKS[1]["url"]


def test_playlist_rejects_bad_scheme() -> None:
    try:
        normalize_playlist({"tracks": [{"url": "ftp://nope"}]})
    except ValueError as exc:
        assert "http" in str(exc).lower() or "/" in str(exc)
        return
    raise AssertionError("expected ValueError")
