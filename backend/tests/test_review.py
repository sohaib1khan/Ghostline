"""Spaced review scheduling branches."""

from datetime import UTC, datetime
from decimal import Decimal
from random import Random

from app.services.review import (
    EASE_MAX,
    EASE_MIN,
    backfill_next_review,
    clamp_ease,
    schedule_after_result,
)


def test_clamp_ease_bounds() -> None:
    assert clamp_ease("1.00") == EASE_MIN
    assert clamp_ease("9.00") == EASE_MAX


def test_pass_without_hints_grows_interval() -> None:
    first = schedule_after_result(
        interval_days=0,
        ease=2.5,
        lapses=0,
        passed=True,
        hints_used=0,
        now=datetime(2026, 1, 1, tzinfo=UTC),
        rng=Random(1),
    )
    assert first.last_result == "pass"
    assert first.interval_days >= 1
    second = schedule_after_result(
        interval_days=1,
        ease=first.ease,
        lapses=0,
        passed=True,
        hints_used=0,
        now=datetime(2026, 1, 2, tzinfo=UTC),
        rng=Random(1),
    )
    assert second.interval_days >= first.interval_days
    assert second.ease >= first.ease


def test_pass_with_hints_slows_growth() -> None:
    state = schedule_after_result(
        interval_days=7,
        ease=2.5,
        lapses=0,
        passed=True,
        hints_used=2,
        now=datetime(2026, 1, 1, tzinfo=UTC),
        rng=Random(2),
    )
    assert state.last_result == "pass_hints"
    assert state.ease < Decimal("2.50")
    assert state.interval_days >= 1


def test_fail_resets_interval_and_counts_lapse() -> None:
    state = schedule_after_result(
        interval_days=35,
        ease=2.8,
        lapses=1,
        passed=False,
        hints_used=0,
        now=datetime(2026, 1, 1, tzinfo=UTC),
        rng=Random(3),
    )
    assert state.last_result == "fail"
    assert state.interval_days == 1
    assert state.lapses == 2
    assert state.ease < Decimal("2.80")


def test_fuzz_stays_within_ten_percent() -> None:
    base = schedule_after_result(
        interval_days=10,
        ease=2.5,
        lapses=0,
        passed=True,
        hints_used=0,
        now=datetime(2026, 1, 1, tzinfo=UTC),
        rng=Random(0),
    )
    # After pass from 10 with ease 2.5 → ~25, fuzzed ±10%.
    assert 20 <= base.interval_days <= 30


def test_backfill_spreads_across_week() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    days = {(backfill_next_review(start, index, 20) - start).days for index in range(20)}
    assert days <= {1, 2, 3, 4, 5, 6, 7}
    assert len(days) >= 5
