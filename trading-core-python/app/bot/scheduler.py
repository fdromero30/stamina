"""Async scheduler for the trading engine."""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from app.bot import persistence

logger = logging.getLogger(__name__)

TickHandler = Callable[[], Awaitable[dict]]


class TradingScheduler:
    """
    A simple async scheduler that runs the trading engine at a fixed interval.

    Can be started, stopped, and queried for status.
    Keeps an in-memory history of recent cycles for observability.
    """

    def __init__(self, interval_seconds: int, history_limit: int = 20) -> None:
        self._interval = interval_seconds
        self._history_limit = history_limit
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._cycle_count = 0
        self._last_run: Optional[datetime] = None
        self._next_run: Optional[datetime] = None
        self._on_tick: Optional[TickHandler] = None
        self._cycle_history: list[dict[str, Any]] = []

        # Restore persisted state
        self._cycle_history = persistence.load_cycle_history(limit=history_limit)
        self._cycle_count = persistence.load_bot_state("cycle_count", 0)
        last_run = persistence.load_bot_state("last_run")
        if last_run:
            try:
                self._last_run = datetime.fromisoformat(last_run)
            except ValueError:
                self._last_run = None
        next_run = persistence.load_bot_state("next_run")
        if next_run:
            try:
                self._next_run = datetime.fromisoformat(next_run)
            except ValueError:
                self._next_run = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_run(self) -> Optional[datetime]:
        return self._last_run

    @property
    def next_run(self) -> Optional[datetime]:
        return self._next_run

    @property
    def interval_seconds(self) -> int:
        return self._interval

    @property
    def cycle_history(self) -> list[dict[str, Any]]:
        """Return the recent cycle history (most recent first)."""
        return self._cycle_history

    def set_tick_handler(self, handler: TickHandler) -> None:
        """Set the async callable that will be invoked on each tick."""
        self._on_tick = handler

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        if self._on_tick is None:
            raise RuntimeError("No tick handler set. Call set_tick_handler() first.")

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Trading scheduler started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        """Stop the scheduler loop gracefully."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Trading scheduler stopped")

    async def trigger_cycle(self) -> dict:
        """Manually trigger a single trading cycle (for testing)."""
        if self._on_tick is None:
            raise RuntimeError("No tick handler set")
        result = await self._run_single_cycle(source="manual")
        self._cycle_count += 1
        self._last_run = datetime.now(timezone.utc)
        self._persist_state()
        return result

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = datetime.now(timezone.utc)
            self._next_run = datetime.fromtimestamp(
                now.timestamp() + self._interval, tz=timezone.utc
            )

            try:
                await self._run_single_cycle(source="auto")
                self._cycle_count += 1
                self._last_run = datetime.now(timezone.utc)
                self._persist_state()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in trading cycle")

            # Wait for the next interval (or until stopped)
            await self._sleep_until_next()

    async def _run_single_cycle(self, source: str) -> dict:
        """Execute one trading cycle and record it in the history."""
        started = time.monotonic()

        if self._on_tick is None:
            raise RuntimeError("No tick handler set")

        try:
            result = await self._on_tick()
            status = "success"
            error = None
        except Exception as e:
            logger.exception("Trading cycle failed")
            result = {
                "evaluations": [],
                "trades": [],
                "adjustments": [],
                "error": str(e),
            }
            status = "error"
            error = str(e)

        duration_ms = round((time.monotonic() - started) * 1000, 2)

        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "duration_ms": duration_ms,
            "status": status,
            "evaluations": result.get("evaluations", []),
            "trades": result.get("trades", []),
            "adjustments": result.get("adjustments", []),
            "skipped": result.get("skipped", False),
            "error": error,
            "reason": result.get("reason"),
        }

        self._cycle_history.insert(0, entry)
        del self._cycle_history[self._history_limit:]

        # Persist the cycle entry to database
        persistence.save_cycle(entry)

        return result

    def _persist_state(self) -> None:
        """Persist scheduler state (cycle count, last/next run) to database."""
        persistence.save_bot_state("cycle_count", self._cycle_count)
        if self._last_run:
            persistence.save_bot_state("last_run", self._last_run.isoformat())
        if self._next_run:
            persistence.save_bot_state("next_run", self._next_run.isoformat())

    async def _sleep_until_next(self) -> None:
        """Sleep for the interval, checking periodically if stopped."""
        slept = 0.0
        while slept < self._interval and self._running:
            await asyncio.sleep(1.0)
            slept += 1.0