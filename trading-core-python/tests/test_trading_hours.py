"""Tests for per-symbol trading hours."""

from datetime import datetime, timezone

from app.bot.trading_hours import (
    is_within_trading_hours,
    seconds_until_next_window,
    trading_hours_for,
)


def _utc(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_eurusd_open_monday_morning():
    # Monday 10:00 UTC → EUR/USD open
    assert is_within_trading_hours("EUR/USD", _utc(2026, 8, 17, 10, 0)) is True


def test_eurusd_closed_saturday():
    # Saturday 12:00 UTC → EUR/USD closed
    assert is_within_trading_hours("EUR/USD", _utc(2026, 8, 22, 12, 0)) is False


def test_eurusd_daily_break_2200_2205():
    # Monday 22:02 UTC → EUR/USD daily break (22:00-22:05)
    assert is_within_trading_hours("EUR/USD", _utc(2026, 8, 17, 22, 2)) is False


def test_eurusd_open_after_break():
    # Monday 22:10 UTC → EUR/USD open again
    assert is_within_trading_hours("EUR/USD", _utc(2026, 8, 17, 22, 10)) is True


def test_gold_open_monday_morning():
    # Monday 10:00 UTC → GOLD open
    assert is_within_trading_hours("GOLD", _utc(2026, 8, 17, 10, 0)) is True


def test_gold_daily_break_2100_2200():
    # Monday 21:30 UTC → GOLD daily break (21:00-22:00)
    assert is_within_trading_hours("GOLD", _utc(2026, 8, 17, 21, 30)) is False


def test_gold_open_after_break():
    # Monday 22:10 UTC → GOLD open again
    assert is_within_trading_hours("GOLD", _utc(2026, 8, 17, 22, 10)) is True


def test_gold_closed_saturday():
    # Saturday 12:00 UTC → GOLD closed
    assert is_within_trading_hours("GOLD", _utc(2026, 8, 22, 12, 0)) is False


def test_unknown_symbol_fail_open():
    # Unknown symbol → allow (fail-open)
    assert is_within_trading_hours("UNKNOWN", _utc(2026, 8, 22, 12, 0)) is True


def test_seconds_until_next_window_saturday():
    # Saturday 12:00 UTC → next window is Sunday 22:00 UTC (GOLD)
    now = _utc(2026, 8, 22, 12, 0)  # Saturday
    secs = seconds_until_next_window("GOLD", now)
    # Saturday 12:00 → Sunday 22:00 = 34 hours = 122400 seconds
    assert secs == 34 * 3600


def test_seconds_until_next_window_when_open():
    # Monday 10:00 UTC → already open → 0
    assert seconds_until_next_window("EUR/USD", _utc(2026, 8, 17, 10, 0)) == 0


def test_trading_hours_for_aliases():
    # XAU/USD resolves to GOLD schedule
    gold_hours = trading_hours_for("XAU/USD")
    assert gold_hours is not None
    assert gold_hours.symbol == "GOLD"
    # EUR/USD resolves to EURUSD schedule
    eurusd_hours = trading_hours_for("EUR/USD")
    assert eurusd_hours is not None
    assert eurusd_hours.symbol == "EURUSD"
