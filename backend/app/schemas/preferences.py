"""Accessibility preferences stored on the user and mirrored in the browser."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TextScale = Literal[100, 125, 150, 175, 200]
CodeScale = Literal[100, 125, 150, 175, 200]
LineSpacing = Literal["normal", "relaxed", "loose"]
Contrast = Literal["calm", "high-dark", "high-light"]
GhostStrength = Literal[30, 45, 60, 75]
CursorStyle = Literal["normal", "thick", "glow"]
FocusRing = Literal["standard", "thick"]


class PreferencesIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reduceMotion: bool | None = None
    sound: bool | None = None
    volume: float | None = Field(default=None, ge=0, le=1)
    textScale: TextScale | None = None
    codeScale: CodeScale | None = None
    lineSpacing: LineSpacing | None = None
    contrast: Contrast | None = None
    ghostStrength: GhostStrength | None = None
    cursorStyle: CursorStyle | None = None
    focusRing: FocusRing | None = None
    dyslexiaSpacing: bool | None = None
    wrapLongLines: bool | None = None
    showWhitespace: bool | None = None
    highContrastTyping: bool | None = None
    editorBodyPx: int | None = Field(default=None, ge=220, le=4000)
    dailyReviews: int | None = Field(default=None, ge=0, le=50)
    dailyLessons: int | None = Field(default=None, ge=0, le=20)


class PreferencesOut(BaseModel):
    reduceMotion: bool = False
    sound: bool = False
    volume: float = 0.4
    textScale: TextScale = 100
    codeScale: CodeScale = 150
    lineSpacing: LineSpacing = "relaxed"
    contrast: Contrast = "calm"
    ghostStrength: GhostStrength = 60
    cursorStyle: CursorStyle = "thick"
    focusRing: FocusRing = "thick"
    dyslexiaSpacing: bool = False
    wrapLongLines: bool = True
    showWhitespace: bool = True
    highContrastTyping: bool = True
    editorBodyPx: int | None = None
    dailyReviews: int = 5
    dailyLessons: int = 1
