"""Tests for per-symbol news relevance filtering (commodities for GOLD)."""

from datetime import datetime, timezone

from app.bot.news_calendar import (
    NewsEvent,
    relevant_events_for_symbol,
    find_active_blackout_for_symbol,
)


def _ev(title, country, impact, day=17, hour=12):
    return NewsEvent(
        title=title,
        country=country,
        event_time_utc=datetime(2026, 8, day, hour, tzinfo=timezone.utc),
        impact=impact,
    )


def _sample_events():
    return [
        _ev("US Non-Farm Payrolls", "USD", "High", 18, 12),
        _ev("ECB Interest Rate Decision", "EUR", "High", 18, 13),
        _ev("Gold Price", "USD", "High", 18, 14),
        _ev("Crude Oil Inventories", "USD", "High", 18, 15),
        _ev("Retail Sales (Low)", "USD", "Medium", 18, 16),
    ]


def test_eurusd_includes_eur_and_usd_high_only():
    events = relevant_events_for_symbol("EUR/USD", _sample_events())
    titles = [e.title for e in events]
    # EUR + USD High events included
    assert "US Non-Farm Payrolls" in titles
    assert "ECB Interest Rate Decision" in titles
    # Commodities NOT relevant to FX
    assert "Gold Price" not in titles
    assert "Crude Oil Inventories" not in titles
    # Medium excluded
    assert all(e.impact == "High" for e in events)


def test_gold_includes_commodities_and_usd():
    events = relevant_events_for_symbol("GOLD", _sample_events())
    titles = [e.title for e in events]
    # USD High + commodity events
    assert "US Non-Farm Payrolls" in titles  # USD High
    assert "Gold Price" in titles  # commodity
    assert "Crude Oil Inventories" in titles  # commodity
    # EUR-only event NOT relevant to gold
    assert "ECB Interest Rate Decision" not in titles
    # Medium excluded
    assert all(e.impact == "High" for e in events)


def test_xauusd_same_as_gold():
    gold = relevant_events_for_symbol("GOLD", _sample_events())
    alias = relevant_events_for_symbol("XAU/USD", _sample_events())
    assert [e.title for e in gold] == [e.title for e in alias]


def test_find_blackout_for_symbol_scoped():
    events = _sample_events()
    now = datetime(2026, 8, 18, 13, 30, tzinfo=timezone.utc)  # 30 min after ECB event
    # Gold should NOT be in blackout for an EUR-only event
    assert find_active_blackout_for_symbol(events, "GOLD", now) is None
    # EUR/USD SHOULD be in blackout (ECB event + 30 min window)
    blackout = find_active_blackout_for_symbol(events, "EUR/USD", now)
    assert blackout is not None
    assert blackout[0].title == "ECB Interest Rate Decision"


def test_gold_in_blackout_for_commodity_event():
    events = _sample_events()
    now = datetime(2026, 8, 18, 14, 30, tzinfo=timezone.utc)  # 30 min after Gold event
    blackout = find_active_blackout_for_symbol(events, "GOLD", now)
    assert blackout is not None
    assert blackout[0].title == "Gold Price"
