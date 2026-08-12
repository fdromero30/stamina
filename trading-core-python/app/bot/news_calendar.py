"""News calendar client for high-impact economic events (EUR/USD blackout)."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


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
    """Parse raw JSON from the calendar feed and keep only EUR/USD High events."""
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
    - ~5 minutes before a scheduled High EUR/USD event (prefetch trigger) →
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
        """
        Return the cached relevant events, refreshing the feed only when one
        of the allowed triggers fires (startup, long idle, pending prefetch
        for a soon-to-start High event, or explicit force).
        """
        now_utc = _as_utc(now)
        should_fetch = force_refresh or self._cache_is_stale(now_utc) or self._should_prefetch(now_utc)
        if should_fetch:
            try:
                await self._fetch()
            except Exception as e:
                logger.warning("News calendar fetch failed: %s", e)
                if not self._cache:
                    if self._fail_mode == "fail_closed":
                        raise
                    logger.warning(
                        "News calendar unavailable and no cache — running in fail-open mode "
                        "(bot continues trading without news blackout)"
                    )
        return list(self._cache)

    async def refresh(self) -> None:
        """Force a fresh fetch (used on bot start / manual trigger)."""
        await self._fetch()

    @property
    def cached_events(self) -> list[NewsEvent]:
        return list(self._cache)

    @property
    def last_fetch_time(self) -> Optional[datetime]:
        return self._last_fetch_time

    def next_upcoming_event(self, now: datetime) -> Optional[NewsEvent]:
        """First High EUR/USD event at or after ``now`` (from the cache)."""
        now_utc = _as_utc(now)
        for ev in self._cache:
            if ev.event_time_utc >= now_utc:
                return ev
        return None

    # ── Internal ────────────────────────────────────────────────────────

    def _cache_is_stale(self, now: datetime) -> bool:
        if self._last_fetch_time is None:
            return True  # startup
        return (now - self._last_fetch_time) >= self._refresh_after_idle

    def _should_prefetch(self, now: datetime) -> bool:
        """
        True when a High EUR/USD event starts within the prefetch window
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

    async def _fetch(self) -> None:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; stamina-trading-bot/1.0)",
            "Accept": "application/json",
        }
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
        logger.info("Fetched news calendar: %d relevant High EUR/USD events", len(events))
