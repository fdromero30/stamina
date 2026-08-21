"""Per-symbol trading hours (UTC).

Trading hours are NOT derived from eToro (the public API does not expose them).
Instead they are defined per-symbol below based on the eToro CFD market hours:

- EUR/USD (Forex): opens Sunday 22:05 UTC, closes Friday 21:30 UTC, with a
  small daily break from 22:00 to 22:05 UTC. Almost 24/5.
- GOLD (XAU/USD): opens Sunday 22:00 UTC, closes Friday 20:30 UTC, with a
  daily break around 21:00–22:00 UTC. Some 24/7 variants with short
  maintenance pauses.

These can be adjusted for holidays/maintenance via the strategy's
``tradingWindowStart``/``tradingWindowEnd`` when configured.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Per-symbol schedule definitions (UTC) ────────────────────────────────

# A day in minutes.
_DAY_MIN = 24 * 60


def _hm(hhmm: str) -> int:
    """Convert "HH:MM" to minutes since midnight."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@dataclass(frozen=True)
class SymbolTradingHours:
    """Trading schedule for one symbol, expressed in UTC wall-clock times.

    A week is modelled as 7 days with minutes 0..10079 (Sunday=0).
    ``opens_weekday``/``closes_weekday`` use Python weekday convention
    (Monday=0, Sunday=6).
    """

    symbol: str
    opens_weekday: int   # Monday=0, Sunday=6 (the day the market opens)
    opens_time: str      # "HH:MM" UTC
    closes_weekday: int  # Friday=4, Sunday=6 (the day the market closes)
    closes_time: str     # "HH:MM" UTC
    # Optional daily break (start inclusive, end exclusive). None → no break.
    daily_break_start: Optional[str] = None
    daily_break_end: Optional[str] = None

    def open_minutes(self) -> int:
        return _hm(self.opens_time)

    def close_minutes(self) -> int:
        return _hm(self.closes_time)

    def break_start_minutes(self) -> Optional[int]:
        return _hm(self.daily_break_start) if self.daily_break_start else None

    def break_end_minutes(self) -> Optional[int]:
        return _hm(self.daily_break_end) if self.daily_break_end else None


# Canonical schedules (all times UTC).
_TRADING_HOURS: dict[str, SymbolTradingHours] = {
    "EURUSD": SymbolTradingHours(
        symbol="EURUSD",
        opens_weekday=6,   # Sunday
        opens_time="22:05",
        closes_weekday=4,  # Friday
        closes_time="21:35",
        daily_break_start="22:00",
        daily_break_end="22:05",
    ),
    "GOLD": SymbolTradingHours(
        symbol="GOLD",
        opens_weekday=6,   # Sunday
        opens_time="22:00",
        closes_weekday=4,  # Friday
        closes_time="20:30",
        daily_break_start="21:00",
        daily_break_end="22:00",
    ),
    "SILVER": SymbolTradingHours(
        symbol="SILVER",
        opens_weekday=6,   # Sunday
        opens_time="22:00",
        closes_weekday=4,  # Friday
        closes_time="20:30",
        daily_break_start="21:00",
        daily_break_end="22:00",
    ),
}


def _canonical_symbol(symbol: str) -> str:
    """Normalize a symbol to the key used in SYMBOL_ALIASES / schedule table."""
    return symbol.upper().replace("/", "").replace("-", "").replace(" ", "").strip()


def _weekday_minutes(dt: datetime) -> int:
    """Convert a datetime to minutes since Sunday 00:00 UTC (0..10079)."""
    weekday = dt.weekday()  # Monday=0, Sunday=6
    # Shift so Sunday=0, Monday=1, ... Saturday=6
    sunday_based = (weekday + 1) % 7
    minutes = dt.hour * 60 + dt.minute
    return sunday_based * _DAY_MIN + minutes


def trading_hours_for(symbol: str) -> Optional[SymbolTradingHours]:
    """Return the trading schedule for a symbol (or None if unknown)."""
    canonical = _canonical_symbol(symbol)
    # Map aliases (XAU/USD → GOLD, EUR/USD → EURUSD) using the same alias set.
    from app.integrations.symbol_resolver import SYMBOL_ALIASES

    resolved = SYMBOL_ALIASES.get(canonical, canonical)
    return _TRADING_HOURS.get(resolved)


def _is_within_schedule(now: datetime, hours: SymbolTradingHours) -> bool:
    """Pure check: is ``now`` (UTC) inside the week schedule (incl. breaks)?"""
    dt = now.astimezone(timezone.utc)
    wk_min = _weekday_minutes(dt)
    open_min = hours.opens_weekday * _DAY_MIN + hours.open_minutes()
    close_min = hours.closes_weekday * _DAY_MIN + hours.close_minutes()

    open_to_close = open_min < close_min  # normal week
    inside_week = open_to_close and open_min <= wk_min < close_min
    if not open_to_close:
        # Cross-midnight open: treat as open on the same day between open and
        # midnight OR before close.
        inside_week = wk_min >= open_min or wk_min < close_min

    if not inside_week:
        return False

    # Daily break check
    bs = hours.break_start_minutes()
    be = hours.break_end_minutes()
    if bs is not None and be is not None:
        day_min = wk_min % _DAY_MIN
        if bs < be and bs <= day_min < be:
            return False

    return True


def is_within_trading_hours(symbol: str, now: datetime) -> bool:
    """Return True if ``symbol`` is tradable at ``now`` (UTC)."""
    hours = trading_hours_for(symbol)
    if hours is None:
        logger.debug("No trading hours configured for %s — allowing trade (fail-open)", symbol)
        return True
    return _is_within_schedule(now, hours)


def seconds_until_next_window(symbol: str, now: datetime) -> int:
    """
    Seconds until the next moment the symbol becomes tradable (0 if open).

    Used by the scheduler to sleep through non-trading periods (weekend, etc.)
    instead of waking up every interval.
    """
    hours = trading_hours_for(symbol)
    if hours is None:
        return 0

    now_utc = now.astimezone(timezone.utc)
    if _is_within_schedule(now_utc, hours):
        return 0

    # Find the next open time: walk forward minute by minute (max 1 week).
    for delta_min in range(1, 7 * 24 * 60 + 1):
        candidate = now_utc + timedelta(minutes=delta_min)
        if _is_within_schedule(candidate, hours):
            return delta_min * 60
    return 7 * 24 * 60 * 60  # fallback: 1 week


# ── Session overlap (London–New York) ────────────────────────────────────
# The bot only trades during the London–NY overlap: Mon–Fri 08:00–12:00 ET.
# Using US/Eastern (or America/New_York) automatically handles DST:
#   * Summer (EDT, UTC-4): 08:00–12:00 ET = 12:00–16:00 UTC
#   * Winter (EST, UTC-5): 08:00–12:00 ET = 13:00–17:00 UTC

DEFAULT_SESSION_OVERLAP_START = "08:00"  # NY time (24h)
DEFAULT_SESSION_OVERLAP_END = "12:00"    # NY time (24h)
DEFAULT_SESSION_OVERLAP_TZ = "US/Eastern"

# Small cache of resolved tz objects so repeated calls avoid re-creating them.
_tz_cache: dict[str, object] = {}


def _resolve_tz(tz_name: str):
    """Resolve ``tz_name`` via pytz, falling back to stdlib zoneinfo.

    Returns ``None`` when no timezone provider is available (the caller then
    uses the approximate fixed-offset fallback).
    """
    cached = _tz_cache.get(tz_name)
    if cached is not None:
        return cached

    resolved = None
    try:
        import pytz  # type: ignore

        resolved = pytz.timezone(tz_name)
    except Exception:
        try:
            from zoneinfo import ZoneInfo

            resolved = ZoneInfo(tz_name)
        except Exception:
            resolved = None

    if resolved is not None:
        _tz_cache[tz_name] = resolved
    return resolved


def _to_session_tz(dt: datetime, tz_name: str) -> datetime:
    """Convert ``dt`` (treat as UTC instant) to the session timezone.

    Handles DST automatically when pytz/zoneinfo is available.  As a last
    resort, approximates ET with a fixed UTC-4 (summer) / UTC-5 (winter)
    offset based on the month.
    """
    dt_utc = dt.astimezone(timezone.utc)
    tz = _resolve_tz(tz_name)
    if tz is not None:
        return dt_utc.astimezone(tz)  # type: ignore[arg-type]
    # Approximate EDT (UTC-4) from April to October, EST (UTC-5) otherwise.
    offset_hours = -4 if 4 <= dt_utc.month <= 10 else -5
    return dt_utc.astimezone(timezone(timedelta(hours=offset_hours)))


def is_within_session_overlap(
    now: datetime,
    start: str = DEFAULT_SESSION_OVERLAP_START,
    end: str = DEFAULT_SESSION_OVERLAP_END,
    tz_name: str = DEFAULT_SESSION_OVERLAP_TZ,
) -> bool:
    """Return True if ``now`` is inside the London–NY session overlap.

    The window is Monday–Friday between ``start`` and ``end`` (exclusive
    end) in the ``tz_name`` zone (default US/Eastern).  Weekends are always
    outside the session.  DST is handled automatically via the timezone.
    """
    dt = _to_session_tz(now, tz_name)
    if dt.weekday() >= 5:  # Saturday / Sunday → no session
        return False
    minutes = dt.hour * 60 + dt.minute
    start_min = _hm(start)
    end_min = _hm(end)
    return start_min <= minutes < end_min


def seconds_until_next_session_overlap(
    now: datetime,
    start: str = DEFAULT_SESSION_OVERLAP_START,
    end: str = DEFAULT_SESSION_OVERLAP_END,
    tz_name: str = DEFAULT_SESSION_OVERLAP_TZ,
) -> int:
    """
    Seconds until the next London–NY session overlap opens (0 if open now).

    Used by the scheduler to sleep through dead periods (outside session,
    weekends, overnight) instead of waking up every interval.
    """
    if is_within_session_overlap(now, start, end, tz_name):
        return 0

    now_utc = now.astimezone(timezone.utc)
    # Walk forward minute by minute (max 8 days covers Fri → next Mon).
    for delta_min in range(1, 8 * 24 * 60 + 1):
        candidate = now_utc + timedelta(minutes=delta_min)
        if is_within_session_overlap(candidate, start, end, tz_name):
            return delta_min * 60
    return 8 * 24 * 60 * 60  # fallback: 8 days
