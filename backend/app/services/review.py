"""Spaced repetition scheduling — pure functions, fully unit-tested."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

EASE_MIN = Decimal("1.30")
EASE_MAX = Decimal("3.00")
INTERVAL_MAX_DAYS = 180
FIRST_STEPS = (1, 3, 7, 16, 35)


@dataclass(frozen=True)
class ReviewState:
    interval_days: int
    ease: Decimal
    lapses: int
    last_result: str | None
    next_review_at: datetime | None


def clamp_ease(ease: Decimal | float | str) -> Decimal:
    value = Decimal(str(ease))
    if value < EASE_MIN:
        return EASE_MIN
    if value > EASE_MAX:
        return EASE_MAX
    return value.quantize(Decimal("0.01"))


def clamp_interval(days: int) -> int:
    return max(1, min(INTERVAL_MAX_DAYS, int(days)))


def _fuzz(days: int, rng: random.Random | None = None) -> int:
    """±10% fuzz so reviews do not clump."""
    roller = rng or random
    if days <= 1:
        return 1
    factor = roller.uniform(0.9, 1.1)
    return clamp_interval(max(1, round(days * factor)))


def schedule_after_result(
    *,
    interval_days: int,
    ease: Decimal | float,
    lapses: int,
    passed: bool,
    hints_used: int,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> ReviewState:
    """Return the next review state after a graded attempt."""
    stamp = now or datetime.now(UTC)
    current_ease = clamp_ease(ease)
    current_interval = max(0, int(interval_days))
    result = "fail"
    next_lapses = lapses

    if not passed:
        next_interval = 1
        next_ease = clamp_ease(current_ease - Decimal("0.20"))
        next_lapses = lapses + 1
        result = "fail"
    elif hints_used > 0:
        next_interval = (
            clamp_interval(max(1, round(current_interval * 1.2))) if current_interval else 1
        )
        next_ease = clamp_ease(current_ease - Decimal("0.15"))
        result = "pass_hints"
    else:
        if current_interval <= 0:
            next_interval = FIRST_STEPS[0]
        elif current_interval in FIRST_STEPS[:-1]:
            next_interval = FIRST_STEPS[FIRST_STEPS.index(current_interval) + 1]
        else:
            next_interval = clamp_interval(max(1, round(current_interval * float(current_ease))))
        next_ease = clamp_ease(current_ease + Decimal("0.10"))
        result = "pass"

    fuzzed = _fuzz(next_interval, rng)
    return ReviewState(
        interval_days=fuzzed,
        ease=next_ease,
        lapses=next_lapses,
        last_result=result,
        next_review_at=stamp + timedelta(days=fuzzed),
    )


def backfill_next_review(completed_at: datetime, index: int, total: int) -> datetime:
    """Spread first reviews over the next 7 days after completion."""
    if total <= 1:
        offset = 1
    else:
        offset = 1 + int(index % 7)
    return completed_at + timedelta(days=offset)
