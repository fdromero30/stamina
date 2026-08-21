"""Tests for the London–NY session overlap filter.

The overlap window is Mon–Fri 08:00–12:00 in New York (US/Eastern).
DST is handled automatically:
  * Summer (EDT, UTC-4): 08:00–12:00 ET = 12:00–16:00 UTC
  * Winter (EST, UTC-5): 08:00–12:00 ET = 13:00–17:00 UTC
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.bot.trading_hours import (
    is_within_session_overlap,
    seconds_until_next_session_overlap,
)

# Default window used by the bot (Mon–Fri 08:00–12:00 US/Eastern).
START = "08:00"
END = "12:00"
TZ = "US/Eastern"


def _utc(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


# ── Summer (EDT, UTC-4) — window is 12:00–16:00 UTC ────────────────


def test_monday_1000_et_summer_is_open():
    # Monday 14:00 UTC = 10:00 ET (EDT) → inside the window
    assert is_within_session_overlap(_utc(2026, 8, 17, 14, 0), START, END, TZ) is True


def test_monday_0800_et_summer_start_inclusive():
    # Monday 12:00 UTC = 08:00 ET (EDT) → window start is inclusive
    assert is_within_session_overlap(_utc(2026, 8, 17, 12, 0), START, END, TZ) is True


def test_monday_1200_et_summer_end_exclusive():
    # Monday 16:00 UTC = 12:00 ET (EDT) → window end is exclusive → closed
    assert is_within_session_overlap(_utc(2026, 8, 17, 16, 0), START, END, TZ) is False


def test_monday_0200_et_summer_closed():
    # Monday 06:00 UTC = 02:00 ET (EDT) → outside the window
    assert is_within_session_overlap(_utc(2026, 8, 17, 6, 0), START, END, TZ) is False


def test_saturday_closed():
    # Saturday 14:00 UTC → weekend, no session
    assert is_within_session_overlap(_utc(2026, 8, 22, 14, 0), START, END, TZ) is False


def test_sunday_closed():
    # Sunday 14:00 UTC → weekend, no session
    assert is_within_session_overlap(_utc(2026, 8, 23, 14, 0), START, END, TZ) is False


# ── Winter (EST, UTC-5) — window is 13:00–17:00 UTC ────────────────


def test_monday_0900_et_winter_is_open():
    # Monday 14:00 UTC = 09:00 ET (EST) → inside the window
    assert is_within_session_overlap(_utc(2026, 1, 5, 14, 0), START, END, TZ) is True


def test_monday_0800_et_winter_start_inclusive():
    # Monday 13:00 UTC = 08:00 ET (EST) → window start is inclusive
    assert is_within_session_overlap(_utc(2026, 1, 5, 13, 0), START, END, TZ) is True


def test_monday_0759_et_winter_closed():
    # Monday 12:59 UTC = 07:59 ET (EST) → one minute before open
    assert is_within_session_overlap(_utc(2026, 1, 5, 12, 59), START, END, TZ) is False


def test_monday_1200_et_winter_end_exclusive():
    # Monday 17:00 UTC = 12:00 ET (EST) → end exclusive → closed
    assert is_within_session_overlap(_utc(2026, 1, 5, 17, 0), START, END, TZ) is False


def test_friday_1600_et_summer_closed():
    # Friday 20:00 UTC = 16:00 ET (EDT) → after 12:00 ET → closed
    assert is_within_session_overlap(_utc(2026, 8, 21, 20, 0), START, END, TZ) is False


# ── seconds_until_next_session_overlap ─────────────────────────────


def test_seconds_until_next_when_open():
    # Monday 14:00 UTC (10:00 ET summer) → already open → 0
    assert seconds_until_next_session_overlap(_utc(2026, 8, 17, 14, 0), START, END, TZ) == 0


def test_seconds_until_next_after_close_same_day():
    # Monday 18:00 UTC (14:00 ET summer) → next window is Tuesday 12:00 UTC
    # 18:00 Monday → 12:00 Tuesday = 18 hours = 64800 seconds
    now = _utc(2026, 8, 17, 18, 0)
    secs = seconds_until_next_session_overlap(now, START, END, TZ)
    assert secs == 18 * 3600


def test_seconds_until_next_before_open_same_day():
    # Monday 06:00 UTC (02:00 ET) → next window is 12:00 UTC same day
    now = _utc(2026, 8, 17, 6, 0)
    secs = seconds_until_next_session_overlap(now, START, END, TZ)
    assert secs == 6 * 3600


def test_seconds_until_next_weekend_friday():
    # Friday 20:00 UTC (16:00 ET summer) → next window Monday 12:00 UTC
    # Friday 20:00 → Monday 12:00 = 64 hours = 230400 seconds
    now = _utc(2026, 8, 21, 20, 0)
    secs = seconds_until_next_session_overlap(now, START, END, TZ)
    assert secs == 64 * 3600


def test_seconds_until_next_saturday():
    # Saturday 12:00 UTC → next window Monday 12:00 UTC
    # Saturday 12:00 → Monday 12:00 = 48 hours = 172800 seconds
    now = _utc(2026, 8, 22, 12, 0)
    secs = seconds_until_next_session_overlap(now, START, END, TZ)
    assert secs == 48 * 3600


def test_seconds_until_next_is_positive_and_dst_aware():
    # Sanity: the returned delta, when added to now, lands inside the window.
    now = _utc(2026, 1, 5, 12, 59)  # Monday 07:59 EST winter
    secs = seconds_until_next_session_overlap(now, START, END, TZ)
    assert secs == 60  # opens at 13:00 UTC (08:00 EST)
    assert is_within_session_overlap(now + timedelta(seconds=secs), START, END, TZ) is True


def test_custom_window_parameters():
    # Custom 09:00–10:00 ET window — Monday 14:00 UTC (10:00 ET) is the end
    # (exclusive) → closed; Monday 13:30 UTC (09:30 ET) → open.
    assert is_within_session_overlap(_utc(2026, 8, 17, 14, 0), "09:00", "10:00", TZ) is False
    assert is_within_session_overlap(_utc(2026, 8, 17, 13, 30), "09:00", "10:00", TZ) is True