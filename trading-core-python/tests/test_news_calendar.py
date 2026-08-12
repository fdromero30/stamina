"""Test suite for the news calendar blackout feature."""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.bot.news_calendar import (
    NewsEvent,
    parse_news_calendar,
    find_active_blackout,
    seconds_until,
    is_time_for_reopen_spread_check,
)


def utc(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def make_event(iso, title="FOMC Statement", country="USD", impact="High"):
    return NewsEvent(
        title=title,
        country=country,
        event_time_utc=datetime.fromisoformat(iso).astimezone(timezone.utc),
        impact=impact,
    )


SAMPLE_JSON = """[
  {"title":"Bank Lending y/y","country":"JPY","date":"2026-08-09T19:50:00-04:00","impact":"Low"},
  {"title":"Sentix Investor Confidence","country":"EUR","date":"2026-08-10T04:30:00-04:00","impact":"Low"},
  {"title":"Non-Farm Payrolls","country":"USD","date":"2026-08-12T12:30:00-04:00","impact":"High"},
  {"title":"ECB Press Conference","country":"EUR","date":"2026-08-12T13:45:00-04:00","impact":"High"},
  {"title":"Cash Rate","country":"AUD","date":"2026-08-11T00:30:00-04:00","impact":"High"}
]"""


def test_parse_filters_to_eur_usd_high():
    events = parse_news_calendar(SAMPLE_JSON)
    titles = {e.title for e in events}
    assert titles == {"Non-Farm Payrolls", "ECB Press Conference"}
    assert all(e.impact == "High" for e in events)
    assert all(e.country in ("EUR", "USD") for e in events)
    nfp = next(e for e in events if e.title == "Non-Farm Payrolls")
    assert nfp.event_time_utc == utc(2026, 8, 12, 16, 30)


def test_parse_handles_malformed_json():
    try:
        parse_news_calendar("{not valid")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_parse_handles_missing_fields():
    events = parse_news_calendar('[{"title":"X","country":"USD"}]')
    assert events == []


def test_find_blackout_inside_window():
    events = [make_event("2026-08-12T16:30:00+00:00")]
    now = utc(2026, 8, 12, 16, 15)
    result = find_active_blackout(events, now, before_minutes=30, after_minutes=30)
    assert result is not None
    ev, start, end = result
    assert ev.title == "FOMC Statement"
    assert start == utc(2026, 8, 12, 16, 0)
    assert end == utc(2026, 8, 12, 17, 0)


def test_find_blackout_outside_window():
    events = [make_event("2026-08-12T16:30:00+00:00")]
    now = utc(2026, 8, 12, 18, 0)
    assert find_active_blackout(events, now, before_minutes=30, after_minutes=30) is None


def test_seconds_until():
    now = utc(2026, 8, 12, 16, 0)
    target = utc(2026, 8, 12, 16, 30)
    assert seconds_until(target, now) == 1800
    past = utc(2026, 8, 12, 15, 0)
    assert seconds_until(past, now) == 0


def test_reopen_spread_check_window():
    events = [make_event("2026-08-12T16:30:00+00:00")]
    # Reopen starts at event+30 (17:00) and grace window is [17:00, 17:05)
    assert is_time_for_reopen_spread_check(events, utc(2026, 8, 12, 17, 2), after_minutes=30, grace_minutes=5) is True
    assert is_time_for_reopen_spread_check(events, utc(2026, 8, 12, 17, 4), after_minutes=30, grace_minutes=5) is True
    assert is_time_for_reopen_spread_check(events, utc(2026, 8, 12, 17, 5), after_minutes=30, grace_minutes=5) is False
    assert is_time_for_reopen_spread_check(events, utc(2026, 8, 12, 17, 35), after_minutes=30, grace_minutes=5) is False
    assert is_time_for_reopen_spread_check(events, utc(2026, 8, 12, 16, 0), after_minutes=30, grace_minutes=5) is False


if __name__ == "__main__":
    tests = [
        test_parse_filters_to_eur_usd_high,
        test_parse_handles_malformed_json,
        test_parse_handles_missing_fields,
        test_find_blackout_inside_window,
        test_find_blackout_outside_window,
        test_seconds_until,
        test_reopen_spread_check_window,
    ]
    passed = 0
    for i, t in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {t.__name__}...")
        t()
        passed += 1
        print()
    print(f"All {passed}/{len(tests)} tests passed!")
