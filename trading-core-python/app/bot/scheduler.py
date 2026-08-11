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
    An async scheduler aligned to closed candle boundaries.

    Instead of running immediately when started (which could operate on an
    incomplete candle), the loop first sleeps until the next multiple of the
    configured interval (e.g. every 5 minutes) plus a small margin, then runs
    the trading cycle on the just-closed candle.  After each cycle it realigns
    to the next boundary so the schedule stays locked to candle openings.

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
        self._run_id: Optional[str] = None

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
        # Start a new execution record (persistent)
        self._run_id = persistence.start_run()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Trading scheduler started (interval=%ds, run=%s)", self._interval, self._run_id)

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
        # Close the execution record ('stopped' normal)
        persistence.finish_run(self._run_id, status="stopped")
        self._run_id = None
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
        """Main scheduler loop, aligned to closed candle boundaries.

        On startup (regardless of the current time), the loop first sleeps
        until the next multiple of ``interval_seconds`` (e.g. 10:55:00 for a
        5m interval) plus a small margin (2s by default) so the candle that
        just closed is fully available.  After each cycle it realigns to the
        next boundary, keeping the schedule locked to candle openings.
        """
        while self._running:
            # ── Align: sleep until the next closed-candle boundary ──
            now = datetime.now(timezone.utc)
            sleep_seconds = self._seconds_until_next_window(now, self._interval)

            self._next_run = datetime.fromtimestamp(
                now.timestamp() + sleep_seconds, tz=timezone.utc
            )
            self._persist_state()

            logger.info(
                "Aligned: sleeping %.1fs until next closed candle boundary (%s)",
                sleep_seconds,
                self._next_run.strftime("%H:%M:%S"),
            )
            await self._sleep_until_next(sleep_seconds)
            if not self._running:
                break

            # ── Run one cycle on the just-closed candle ──
            try:
                result = await self._run_single_cycle(source="auto")
                self._cycle_count += 1
                self._last_run = datetime.now(timezone.utc)

                # If the engine reports it is outside trading hours (e.g.
                # weekend), sleep until the next trading window opens instead
                # of staying aligned to candle boundaries in a closed market.
                next_in = result.get("next_run_seconds")
                if result.get("skipped") and isinstance(next_in, (int, float)) and next_in > 0:
                    sleep_seconds = int(next_in)
                    logger.info(
                        "Cycle skipped; sleeping %.1f hours until next trading window",
                        sleep_seconds / 3600,
                    )
                    self._next_run = datetime.fromtimestamp(
                        datetime.now(timezone.utc).timestamp() + sleep_seconds,
                        tz=timezone.utc,
                    )
                    self._persist_state()
                    await self._sleep_until_next(sleep_seconds)
                    continue
                self._persist_state()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in trading cycle")

    @staticmethod
    def _seconds_until_next_window(
        now: datetime,
        interval_seconds: int,
        margin_seconds: int = 2,
    ) -> int:
        """Seconds until the next aligned boundary (closed candle) + margin.

        Example (interval=300, margin=2):
          now=10:53:40 → next boundary 10:55:00 → returns 142 (10:55:02)
          now=10:55:01 → next boundary 11:00:00 → returns 301 (11:00:02)

        The margin ensures the candle that just closed is fully available in
        the eToro feed before we consume it.
        """
        epoch = int(now.timestamp())
        next_boundary = ((epoch // interval_seconds) + 1) * interval_seconds
        diff = next_boundary + margin_seconds - epoch
        return max(diff, 1)

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

        # Persist the cycle entry to database (associated with the active run)
        persistence.save_cycle(entry, run_id=self._run_id)
        persistence.increment_run_cycles(self._run_id)

        return result

    def _persist_state(self) -> None:
        """Persist scheduler state (cycle count, last/next run) to database."""
        persistence.save_bot_state("cycle_count", self._cycle_count)
        if self._last_run:
            persistence.save_bot_state("last_run", self._last_run.isoformat())
        if self._next_run:
            persistence.save_bot_state("next_run", self._next_run.isoformat())

    async def _sleep_until_next(self, seconds: Optional[int] = None) -> None:
        """Sleep for the given duration, checking periodically if stopped.

        ``seconds`` defaults to the configured interval when not provided.
        This allows the scheduler to sleep for an extended period (e.g. the
        weekend) when the engine reports it is outside trading hours.
        """
        duration = float(seconds if seconds is not None else self._interval)
        slept = 0.0
        while slept < duration and self._running:
            await asyncio.sleep(1.0)
            slept += 1.0
