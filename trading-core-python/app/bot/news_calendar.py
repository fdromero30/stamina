"""News calendar client for high-impact economic events (per-symbol blackout).

Supports per-symbol relevance filters:
- EUR/USD (and FX pairs): countries (EUR, USD), impact High.
- GOLD / SILVER (commodities): USD High events + commodity-specific events
  whose title mentions Gold, Silver, Crude Oil, Oil, Commodity, etc.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# ── Commodity keywords used to match events relevant to GOLD/SILVER ──────
COMMODITY_KEYWORDS: tuple[str, ...] = (
    "gold",
    "gol",       # typo-safe for GOLD
    "silver",
    "crude",
    "oil",
    "commodit",
    "copper",
    "palladium",
    "platinum",
)

# Symbols whose relevance filter includes commodity keywords.
_COMMODITY_SYMBOLS: frozenset[str] = frozenset(
    {"GOLD", "SILVER", "XAUUSD", "XAU/USD", "XAGUSD", "XAG/USD"}
)
# Symbols treated as classic FX (EUR + USD events).
_FX_SYMBOLS: frozenset[str] = frozenset(
    {"EURUSD", "EUR/USD", "GBPUSD", "GBP/USD", "USDJPY", "USD/JPY",
     "AUDUSD", "AUD/USD", "USDCAD", "USD/CAD", "USDCHF", "USD/CHF",
     "NZDUSD", "NZD/USD"}
)


@dataclass(frozen=True)
class NewsEvent:
    """A single economic calendar event."""
    title: str
    country: str
    event_time_utc: datetime
    impact: str


# ── Pure parsing ─────────────────────────────────────────────────────────


def parse_news_calendar(
    raw: str,
    relevant_countries: tuple[str, ...] = ("EUR", "USD"),
    relevant_impacts: tuple[str, ...] = ("High",),
) -> list[NewsEvent]:
    """Parse raw JSON from the calendar feed and keep only matching events."""
    import json

    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of events")

    events: list[NewsEvent] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        country = item.get("country") or ""
        impact = item.get("impact") or ""
        date_str = item.get("date") or ""

        if country not in relevant_countries:
            continue
        if impact not in relevant_impacts:
            continue
        try:
            dt = datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            logger.warning("Skipping event with unparseable date %r: %s", date_str, title)
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        events.append(NewsEvent(
            title=title,
            country=country,
            event_time_utc=dt,
            impact=impact,
        ))

    events.sort(key=lambda e: e.event_time_utc)
    return events


def _as_utc(dt: datetime) -> datetime:
    """Coerce a datetime to UTC (assumes UTC when naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def find_active_blackout(
    events: list[NewsEvent],
    now: datetime,
    before_minutes: int = 30,
    after_minutes: int = 30,
) -> Optional[tuple[NewsEvent, datetime, datetime]]:
    """
    Return (event, window_start, window_end) if ``now`` is inside
    [event_time - before_minutes, event_time + after_minutes] for any event.

    Overlapping windows are merged so the bot does not briefly re-open
    between two back-to-back High events.
    """
    now_utc = _as_utc(now)
    intervals: list[tuple[NewsEvent, datetime, datetime]] = []
    for ev in events:
        start = ev.event_time_utc - timedelta(minutes=before_minutes)
        end = ev.event_time_utc + timedelta(minutes=after_minutes)
        intervals.append((ev, start, end))

    intervals.sort(key=lambda t: t[1])

    merged: list[tuple[NewsEvent, datetime, datetime]] = []
    for ev, start, end in intervals:
        if merged and start <= merged[-1][2]:
            prev_ev, prev_start, prev_end = merged[-1]
            merged[-1] = (prev_ev, prev_start, max(prev_end, end))
        else:
            merged.append((ev, start, end))

    for ev, start, end in merged:
        if start <= now_utc <= end:
            return ev, start, end
    return None


def _normalize_symbol(symbol: str) -> str:
    """Normalize a user symbol for comparison (upper, no slashes/spaces)."""
    return symbol.upper().replace("/", "").replace("-", "").replace(" ", "").strip()


def relevant_events_for_symbol(
    symbol: str,
    events: list[NewsEvent],
) -> list[NewsEvent]:
    """Filter calendar events to those relevant for ``symbol``."""
    norm = _normalize_symbol(symbol)
    alias_map = {
        "XAUUSD": "GOLD",
        "XAU/USD": "GOLD",
        "GOLD": "GOLD",
        "XAGUSD": "SILVER",
        "XAG/USD": "SILVER",
        "SILVER": "SILVER",
        "EUR/USD": "EURUSD",
        "EURUSD": "EURUSD",
    }
    resolved = alias_map.get(norm, norm)

    if resolved in _COMMODITY_SYMBOLS or resolved in {"GOLD", "SILVER"}:
        # Relevant: USD/High events + commodity events whose title mentions
        # gold/silver/oil/etc.
        out: list[NewsEvent] = []
        for ev in events:
            if ev.impact != "High":
                continue
            title_lower = ev.title.lower()
            is_usd = ev.country == "USD"
            is_commodity = any(kw in title_lower for kw in COMMODITY_KEYWORDS)
            if is_usd or is_commodity:
                out.append(ev)
        return out

    if resolved in _FX_SYMBOLS:
        return [e for e in events if e.country in ("EUR", "USD") and e.impact == "High"]

    # Unknown symbol → fall back to EUR/USD behaviour (FX event filter).
    return [e for e in events if e.country in ("EUR", "USD") and e.impact == "High"]


def find_active_blackout_for_symbol(
    events: list[NewsEvent],
    symbol: str,
    now: datetime,
    before_minutes: int = 30,
    after_minutes: int = 30,
) -> Optional[tuple[NewsEvent, datetime, datetime]]:
    """Wrapper: blackout check scoped to a symbol's relevant events."""
    relevant = relevant_events_for_symbol(symbol, events)
    return find_active_blackout(relevant, now, before_minutes, after_minutes)


def symbols_events_for_symbol(symbol: str, events: list[NewsEvent]) -> list[NewsEvent]:
    """Return events relevant to ``symbol`` (commodities included for GOLD)."""
    return relevant_events_for_symbol(symbol, events)


def seconds_until(target: datetime, now: datetime) -> int:
    """Whole seconds between now and target (0 if target is in the past)."""
    delta = target - _as_utc(now)
    return max(0, int(delta.total_seconds()))


def is_time_for_reopen_spread_check(
    events: list[NewsEvent],
    now: datetime,
    after_minutes: int = 30,
    grace_minutes: int = 5,
) -> bool:
    """
    True when ``now`` is inside [event_time + after_minutes,
    event_time + after_minutes + grace_minutes] for a recent High event.

    This is the window the engine uses to confirm the spread is back to
    normal before resuming normal trading after a blackout.
    """
    now_utc = _as_utc(now)
    for ev in events:
        reopen_start = ev.event_time_utc + timedelta(minutes=after_minutes)
        reopen_end = reopen_start + timedelta(minutes=grace_minutes)
        if reopen_start <= now_utc < reopen_end:
            return True
    return False


# ── HTTP client with cache ───────────────────────────────────────────────


class NewsCalendarClient:
    """
    Fetches and caches the weekly economic calendar.

    Request strategy (minimize HTTP calls to avoid IP blocking):
    - On first use (empty cache) → HTTP fetch.
    - After ``refresh_after_idle_minutes`` without a fetch (e.g. long sleep
      over the weekend) → HTTP fetch.
    - ~5 minutes before a scheduled High event (prefetch trigger) →
      HTTP fetch to confirm the event is still programmed.
    - Between those triggers, the cache is used — zero HTTP requests.

    On fetch failure: use the previous successful payload if available;
    otherwise behave according to ``fail_mode`` ("fail_open" → [] with
    warning, "fail_closed" → raise).
    """

    def __init__(
        self,
        url: str = DEFAULT_CALENDAR_URL,
        relevant_countries: tuple[str, ...] = ("EUR", "USD"),
        relevant_impacts: tuple[str, ...] = ("High",),
        refresh_after_idle_minutes: int = 60,
        fail_mode: str = "fail_open",
        timeout_seconds: int = 15,
    ) -> None:
        self._url = url
        self._relevant_countries = relevant_countries
        self._relevant_impacts = relevant_impacts
        self._refresh_after_idle = timedelta(minutes=refresh_after_idle_minutes)
        self._fail_mode = fail_mode
        self._timeout = timeout_seconds

        self._cache: list[NewsEvent] = []
        self._last_fetch_time: Optional[datetime] = None
        # Events already verified in this session (crossed the prefetch
        # threshold and got a fresh fetch).
        self._verified_event_keys: set[tuple[str, str]] = set()

    # ── Public API ─────────────────────────────────────────────────────

    async def get_relevant_events(self, now: datetime, force_refresh: bool = False) -> list[NewsEvent]:
        """Return the cached relevant events (all filter matches)."""
        now_utc = _as_utc(now)
        should_fetch = force_refresh or self._cache_is_stale(now_utc) or self._should_prefetch(now_utc)
        if should_fetch:
            await self._fetch()
        return list(self._cache)

    async def get_relevant_events_for_symbol(
        self,
        symbol: str,
        now: datetime,
        force_refresh: bool = False,
    ) -> list[NewsEvent]:
        """
        Return the cached events relevant to ``symbol`` (e.g. GOLD includes
        commodity events; EUR/USD includes EUR+USD High events).
        """
        all_events = await self.get_relevant_events(now, force_refresh=force_refresh)
        return symbols_events_for_symbol(symbol, all_events)

    async def refresh(self) -> None:
        """Force a fresh fetch (used on bot start / manual trigger)."""
        await self._fetch(raise_on_error=True)

    @property
    def cached_events(self) -> list[NewsEvent]:
        return list(self._cache)

    @property
    def last_fetch_time(self) -> Optional[datetime]:
        return self._last_fetch_time

    def next_upcoming_event(self, now: datetime, symbol: Optional[str] = None) -> Optional[NewsEvent]:
        """First High event at or after ``now`` (optionally filtered by symbol)."""
        now_utc = _as_utc(now)
        events = self._cache
        if symbol is not None:
            events = symbols_events_for_symbol(symbol, events)
        for ev in events:
            if ev.event_time_utc >= now_utc:
                return ev
        return None

    # ── Internal ────────────────────────────────────────────────────────

    async def _fetch(self, raise_on_error: bool = False) -> None:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; stamina-trading-bot/1.0)",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(self._url, headers=headers)
                resp.raise_for_status()
                raw = resp.text
            events = parse_news_calendar(
                raw,
                relevant_countries=self._relevant_countries,
                relevant_impacts=self._relevant_impacts,
            )
            self._cache = events
            self._last_fetch_time = datetime.now(timezone.utc)
            logger.info("Fetched news calendar: %d relevant High events", len(events))
        except Exception as e:
            if raise_on_error or (self._fail_mode == "fail_closed" and not self._cache):
                raise
            if not self._cache:
                logger.warning(
                    "News calendar unavailable and no cache — running in fail-open mode "
                    "(bot continues trading without news blackout): %s",
                    e,
                )

    def _cache_is_stale(self, now: datetime) -> bool:
        if self._last_fetch_time is None:
            return True  # startup
        return (now - self._last_fetch_time) >= self._refresh_after_idle

    def _should_prefetch(self, now: datetime) -> bool:
        """
        True when a High event starts within the prefetch window
        (event_time − (blackout_before + prefetch_minutes)) and has not been
        verified yet this session.
        """
        prefetch_lead = timedelta(minutes=5 + 30)  # 5 min before the 30-min blackout
        for ev in self._cache:
            target = ev.event_time_utc - prefetch_lead
            if target <= now <= ev.event_time_utc:
                key = (ev.event_time_utc.isoformat(), ev.title)
                if key not in self._verified_event_keys:
                    self._verified_event_keys.add(key)
                    logger.info(
                        "Prefetching news calendar for upcoming High event: %s (%s) at %s",
                        ev.title, ev.country, ev.event_time_utc.isoformat(),
                    )
                    return True
        return False