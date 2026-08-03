"""Async scheduler for the trading engine."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class TradingScheduler:
    """
    A simple async scheduler that runs the trading engine at a fixed interval.

    Can be started, stopped, and queried for status.
    """

    def __init__(self, interval_seconds: int) -> None:
        self._interval = interval_seconds
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._cycle_count = 0
        self._last_run: Optional[datetime] = None
        self._next_run: Optional[datetime] = None
        self._on_tick = None

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

    def set_tick_handler(self, handler) -> None:
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
        result = await self._on_tick()
        self._cycle_count += 1
        self._last_run = datetime.now(timezone.utc)
        return result

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = datetime.now(timezone.utc)
            self._next_run = datetime.fromtimestamp(
                now.timestamp() + self._interval, tz=timezone.utc
            )

            try:
                await self._on_tick()
                self._cycle_count += 1
                self._last_run = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in trading cycle")

            # Wait for the next interval (or until stopped)
            await self._sleep_until_next()

    async def _sleep_until_next(self) -> None:
        """Sleep for the interval, checking periodically if stopped."""
        slept = 0.0
        while slept < self._interval and self._running:
            await asyncio.sleep(1.0)
            slept += 1.0