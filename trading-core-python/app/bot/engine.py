"""Deterministic trading engine - the core orchestrator."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

from app.bot import persistence
from app.bot.news_calendar import (
    NewsCalendarClient,
    NewsEvent,
    find_active_blackout_for_symbol,
    is_time_for_reopen_spread_check,
    seconds_until,
    symbols_events_for_symbol,
)
from app.bot.pip_size import infer_pip_size_from_candles
from app.bot.trading_hours import (
    is_within_trading_hours as is_symbol_within_trading_hours,
    seconds_until_next_window as symbol_seconds_until_next_window,
    is_within_session_overlap,
    seconds_until_next_session_overlap,
)
from app.bot.signals import (
    Signal,
    SignalAction,
    Candle,
    MarketData,
    StrategyConfig,
    evaluate_ma_strategy,
    calculate_breakeven_stop_loss,
    calculate_take_profit,
    compute_sma,
    compute_atr,
    find_swing_low,
    find_swing_high,
)
from app.integrations.market_data_client import MarketDataClient
from app.integrations.orders_client import EtoroHttpClient
from app.integrations.strategies_client import StrategiesClient, StrategyConfigDTO
from app.integrations.symbol_resolver import SymbolResolver
from app.risk import PositionRiskManager, PositionRiskState
from app.risk.state_machine import compute_risk_from_price
from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class PortfolioSnapshot:
    """Authoritative eToro state for one user, captured at cycle start.

    Used for ALL entry decisions (position counts, available balance,
    committed risk). Never estimated from local memory.
    """

    user_id: str
    fetched_at: Optional[datetime] = None
    available_balance: float = 0.0
    positions: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_error(self) -> bool:
        return self.error is not None or self.available_balance <= 0

    def count_for_instrument(self, instrument_id: int) -> int:
        """Count open eToro positions on a specific instrument (by ID)."""
        count = 0
        for p in self.positions:
            try:
                if int(p.get("instrumentID")) == instrument_id:
                    count += 1
            except (TypeError, ValueError):
                continue
        return count

# Try to import pytz for timezone support; fallback to UTC offset
try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    # Always bind ``pytz`` (to None) so Pylance never sees it as
    # "possibly unbound" — the ``HAS_PYTZ and pytz is not None`` guards
    # keep the runtime safe.
    pytz = None  # type: ignore[assignment]
    HAS_PYTZ = False
    logger.warning("pytz not available, trading hours check will use UTC")


class TradingBotEngine:
    """
    Deterministic trading engine that orchestrates the full trading cycle.

    Flow per cycle:
    1. Fetch enabled strategies from Java backend
    2. For each strategy: fetch market data + candles
    3. Evaluate signal using pure functions (signals.py)
    4. If signal is BUY/SELL, execute via Java backend (POST /orders/execute-smart)
    5. Check open positions for breakeven adjustments
    """

    def __init__(
        self,
        strategies_client: StrategiesClient,
        market_data_client: MarketDataClient,
        etoro_http_client: EtoroHttpClient,
        base_url: str,
        news_client: Optional[NewsCalendarClient] = None,
    ) -> None:
        self._strategies_client = strategies_client
        self._market_data_client = market_data_client
        self._etoro_http_client = etoro_http_client
        self._base_url = base_url.rstrip("/")
        self._news_client = news_client or NewsCalendarClient(
            url=settings.news_calendar_url,
            refresh_after_idle_minutes=settings.news_refresh_after_idle_minutes,
            fail_mode=settings.news_fetch_fail_mode,
        )
        # Track which blackout event we already handled (protection applied
        # only once per event window).
        self._handled_blackout_key: Optional[str] = None
        # Number of consecutive cycles skipped due to a wide spread after reopen.
        self._reopen_spread_retries = 0
        # Shared symbol resolver (optional; set by main.py).  Uses the same
        # cache as the chart endpoint so symbol mapping is consistent.
        self.symbol_resolver: Optional[SymbolResolver] = None

        # In-memory tracker for open positions (per user)
        # { user_id: [ { position_id, entry_price, stop_loss, take_profit, is_buy, ... } ] }
        self._open_positions: dict[str, list[dict[str, Any]]] = {}

        # Restore persisted open positions
        self._open_positions = persistence.load_open_positions()

        # Authoritative eToro portfolio snapshot per user, refreshed every
        # cycle. Decisions (open counts, balance, committed risk) read THIS,
        # never the in-memory cache.
        self._portfolio_snapshot: dict[str, PortfolioSnapshot] = {}
        # Raw open positions reported by eToro (all instruments, before the
        # strategy filter) — for observability in /bot/cycles.
        self._etoro_positions_by_user: dict[str, list[dict[str, Any]]] = {}
        self._etoro_synced_at: Optional[datetime] = None
        self._last_etoro_error: Optional[str] = None

        # eToro rejection cooldown: key = (user_id, symbol)
        self._reject_counters: dict[tuple[str, str], int] = {}
        self._suspended_until: dict[tuple[str, str], datetime] = {}

        # Transversal risk manager — reuse any strategy's positions
        self._risk_manager = PositionRiskManager(
            etoro_http_client=self._etoro_http_client,
            market_data_client=self._market_data_client,
            candle_interval=settings.default_candle_interval,
            candle_count=settings.default_candle_count,
        )

    @property
    def open_positions(self) -> dict[str, list[dict[str, Any]]]:
        """Return the in-memory open positions tracker (per user)."""
        return self._open_positions

    @property
    def portfolio_snapshot(self) -> dict[str, PortfolioSnapshot]:
        """Authoritative eToro state per user (positions + balance)."""
        return self._portfolio_snapshot

    @property
    def etoro_positions_by_user(self) -> dict[str, list[dict[str, Any]]]:
        """Raw open positions reported by eToro per user (observability)."""
        return self._etoro_positions_by_user

    @property
    def etoro_synced_at(self) -> Optional[str]:
        """ISO timestamp of the last successful eToro reconciliation."""
        return self._etoro_synced_at.isoformat() if self._etoro_synced_at else None

    @property
    def last_etoro_error(self) -> Optional[str]:
        """Last error talking to eToro (None if the last sync was clean)."""
        return self._last_etoro_error

    @property
    def news_client(self) -> NewsCalendarClient:
        """Return the news calendar client (for observability / status)."""
        return self._news_client

    async def get_active_strategy(self) -> dict[str, Any]:
        """Return the strategy currently active (or the default hardcoded one)."""
        try:
            strategies = await self._strategies_client.get_strategies()
            enabled = [s for s in strategies if s.enabled]
            if enabled:
                s = enabled[0]
                return {
                    "id": s.id,
                    "name": s.name,
                    "symbol": s.symbol,
                    "is_default": False,
                }
        except Exception as e:
            logger.warning("Failed to fetch strategies for status: %s", e)

        return {
            "id": "default-ma200-ma9",
            "name": "MA200 + MA9 Crossover (Default)",
            "symbol": "EUR/USD",
            "is_default": True,
        }

    async def run_trading_cycle(self) -> dict[str, Any]:
        """
        Execute a single trading cycle for all enabled strategies.

        Trading hours, news blackouts, spread filters and position limits are
        all checked PER STRATEGY (per symbol) inside ``_evaluate_single_strategy``,
        so EUR/USD and GOLD can run in parallel with their own schedules.
        """
        logger.info("Starting trading cycle...")

        results: dict[str, Any] = {
            "evaluations": [],
            "trades": [],
            "adjustments": [],
        }

        # ── Global session filter (London–NY overlap) ──────────────────
        # New trades are ONLY allowed during the London–NY session overlap
        # (Mon–Fri 08:00–12:00 ET).  Outside that window the cycle is skipped
        # at the ROOT so the scheduler sleeps until the next session opening
        # instead of waking every interval in dead periods.  If configured,
        # open positions are still risk-managed below (Option A).
        if settings.session_overlap_enabled:
            now_utc = datetime.now(timezone.utc)
            if not is_within_session_overlap(
                now_utc,
                start=settings.session_overlap_start,
                end=settings.session_overlap_end,
                tz_name=settings.session_overlap_timezone,
            ):
                next_in = seconds_until_next_session_overlap(
                    now_utc,
                    start=settings.session_overlap_start,
                    end=settings.session_overlap_end,
                    tz_name=settings.session_overlap_timezone,
                )
                results["skipped"] = True
                results["next_run_seconds"] = next_in
                results["reason"] = (
                    "Outside London–NY session overlap — "
                    "next window in %.1fh" % (next_in / 3600)
                )
                logger.info(
                    "%s — sleeping %.1fh (next session 08:00 ET)",
                    results["reason"], next_in / 3600,
                )

                # Option A: keep managing open positions (breakeven/trailing)
                # outside the session window so SL/TP protections still work.
                if settings.session_overlap_manage_positions_outside:
                    # Reconcile first: eToro may have closed positions (TP/SL)
                    # while we were outside the window. Without this, stale
                    # positions stay in memory (and in the UI) even though they
                    # no longer exist in eToro or anywhere else.
                    try:
                        await self._sync_open_positions()
                    except Exception:
                        logger.exception(
                            "Position reconciliation failed while outside session window"
                        )
                    try:
                        await self._check_risk_adjustments(results)
                    except Exception:
                        logger.exception(
                            "Risk adjustments failed while outside session window"
                        )

                return results

        try:
            # 1. Fetch all enabled strategies
            try:
                strategies = await self._strategies_client.get_strategies()
                enabled = [s for s in strategies if s.enabled]
            except Exception as e:
                logger.warning("Failed to fetch strategies from backend: %s. Using default strategy.", e)
                strategies = []
                enabled = []

            if not enabled:
                logger.info("No enabled strategies found, using default hardcoded strategy")
                # Bypass: use a default hardcoded strategy so the bot can be tested
                enabled = [self._default_strategy()]
                results["reason"] = "Using default hardcoded strategy (MA200 + MA9 EUR/USD)"

            logger.info("Found %d enabled strategies", len(enabled))

            # 2. Group strategies by user_id for efficient processing
            user_strategies: dict[str, list[StrategyConfigDTO]] = {}
            for s in enabled:
                uid = s.user_id
                if uid not in user_strategies:
                    user_strategies[uid] = []
                user_strategies[uid].append(s)

            # 3. Reconcile open positions with eToro before processing
            await self.sync_positions_from_etoro(enabled)

            # 3b. Capture the authoritative eToro portfolio snapshot per user
            # (positions + available balance). ALL entry decisions for this
            # cycle read this snapshot — never the local memory cache.
            for user_id in user_strategies:
                try:
                    self._portfolio_snapshot[user_id] = await self._build_portfolio_snapshot(
                        user_id
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to capture eToro snapshot for user %s: %s", user_id, e
                    )
                await asyncio.sleep(0)

            # 4. Process each user's strategies
            for user_id, user_strats in user_strategies.items():
                await self._process_user_strategies(
                    user_id=user_id,
                    strategies=user_strats,
                    results=results,
                )

            # 5. Check open positions for risk-state adjustments (breakeven,
            #    secured profits, trailing ATR) — transversal risk module.
            await self._check_risk_adjustments(results)

        except Exception:
            logger.exception("Fatal error in trading cycle")
            results["error"] = "Trading cycle failed"

        logger.info(
            "Trading cycle complete: %d evaluations, %d trades, %d adjustments",
            len(results["evaluations"]),
            len(results["trades"]),
            len(results["adjustments"]),
        )
        return results

    # ── Internal: Position Reconciliation with eToro ─────────────────────

    def _default_strategy(self) -> StrategyConfigDTO:
        """Fallback strategy used when the backend has no enabled strategies."""
        return StrategyConfigDTO(
            id="default-ma200-ma9",
            user_id="00000000-0000-0000-0000-000000000000",
            user_display_name="Default",
            name="MA200 + MA9 Crossover (Default)",
            symbol="EUR/USD",
            max_position_size=None,
            enabled=True,
            max_drawdown=None,
            max_risk_per_trade=None,
            max_daily_loss=None,
            max_open_positions=2,
            stop_loss=None,
            take_profit=None,
            spread_threshold=None,
            trading_window_start=None,
            trading_window_end=None,
            trailing_stop_activation=None,
            break_even_trigger=1.5,
            use_ml=False,
            ml_strategy_code=None,
        )

    async def _sync_open_positions(self) -> None:
        """Reconcile local open positions (memory + DB) with eToro.

        Fetches the enabled strategies itself so it can be called even when
        the main cycle has already returned early (e.g. outside the London–NY
        session window), guaranteeing the UI never keeps stale positions that
        eToro already closed.
        """
        try:
            strategies = await self._strategies_client.get_strategies()
            enabled = [s for s in strategies if s.enabled]
        except Exception as e:
            logger.warning(
                "Failed to fetch strategies for reconciliation: %s. Using default.",
                e,
            )
            enabled = []
        if not enabled:
            enabled = [self._default_strategy()]
        await self.sync_positions_from_etoro(enabled)

    async def _reconcile_orphan_attempts(self) -> None:
        """Resolve placement attempts left in 'placing' (process died mid-flight).

        Each attempt reserved a client_order_ref BEFORE calling eToro. Here we
        ask eToro whether the position actually exists: if yes → mark the
        attempt open (and re-import the position), if no → mark it failed.
        This closes the atomicity hole between "reserve" and "confirm".
        """
        try:
            attempts = persistence.load_placing_attempts()
        except Exception as e:
            logger.warning("Failed to load placing attempts: %s", e)
            return
        if not attempts:
            return

        logger.warning(
            "Reconciling %d orphaned placement attempt(s) with eToro", len(attempts)
        )
        for attempt in attempts:
            uid = attempt["user_id"]
            ref = attempt["client_order_ref"]
            instrument_id = attempt.get("instrument_id")
            is_buy = bool(attempt.get("is_buy"))
            created_at = attempt.get("created_at") or ""
            try:
                positions = await self._etoro_http_client.get_open_positions(uid)
            except Exception as e:
                logger.warning(
                    "Cannot resolve orphan attempt %s (eToro unreachable): %s", ref, e
                )
                continue

            # Find a position whose instrument + side matches and was opened
            # at/after the attempt was created (avoids matching an older one).
            match = None
            for p in positions:
                try:
                    p_inst = int(p.get("instrumentID"))
                    p_stamp = str(p.get("openDateTime") or "")
                except (TypeError, ValueError):
                    continue
                if instrument_id is not None and p_inst != instrument_id:
                    continue
                if bool(p.get("isBuy", False)) != is_buy:
                    continue
                if created_at and p_stamp and p_stamp < created_at:
                    continue
                match = p
                break

            if match is not None:
                await self._resolve_orphan_match(uid, ref, match, is_buy)
            else:
                logger.warning(
                    "Orphan attempt %s (instrument=%s) NOT found in eToro — marking failed",
                    ref, instrument_id,
                )
                try:
                    persistence.resolve_position_attempt(
                        ref, status="failed",
                        error="position not found in eToro during orphan reconciliation",
                    )
                except Exception as e:
                    logger.warning("Failed to resolve orphan attempt %s: %s", ref, e)

    async def _resolve_orphan_match(
        self,
        uid: str,
        ref: str,
        match: dict[str, Any],
        is_buy: bool,
    ) -> None:
        """Import an orphan-recovered eToro position into memory + DB."""
        pid = int(match.get("positionID"))
        logger.warning(
            "Orphan attempt %s resolved: position %s EXISTS in eToro — marking open",
            ref, pid,
        )
        try:
            persistence.resolve_position_attempt(
                ref, status="open", position_id=pid, response_json=match,
            )
        except Exception as e:
            logger.warning("Failed to resolve orphan attempt %s: %s", ref, e)

        entry = float(match.get("openRate") or 0)
        if entry <= 0:
            return
        position = {
            "position_id": pid,
            "entry_price": entry,
            "stop_loss": None,
            "take_profit": None,
            "is_buy": is_buy,
            "breakeven_applied": False,
            "opened_at": match.get("openDateTime") or datetime.now(timezone.utc).isoformat(),
            "symbol": None,
            "state": 0,
            "sl_original": None,
            "tp_fixed": None,
            "highest_price": None,
            "lowest_price": None,
            "spread_real": None,
            "order_type": "market",
            "units": 0.0,
            "is_pending_order": False,
            "source": "orphan_reconcile",
        }
        open_list = self._open_positions.setdefault(uid, [])
        if all(p.get("position_id") != pid for p in open_list):
            open_list.append(position)
            try:
                persistence.save_position(uid, position)
            except Exception as e:
                logger.warning(
                    "Failed to persist orphan-recovered position %s: %s", pid, e
                )

    def _is_symbol_suspended(self, user_id: str, symbol: str) -> Optional[int]:
        """Return remaining suspension seconds for (user, symbol), or None."""
        key = (user_id, symbol)
        until = self._suspended_until.get(key)
        if until is None:
            return None
        remaining = (until - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            # Backoff expired → clear counters so trading resumes.
            self._suspended_until.pop(key, None)
            self._reject_counters.pop(key, None)
            return None
        return int(remaining)

    def _register_rejection(self, user_id: str, symbol: str, message: str) -> None:
        """Count a consecutive eToro rejection; suspend the symbol after N."""
        key = (user_id, symbol)
        counter = self._reject_counters.get(key, 0) + 1
        self._reject_counters[key] = counter
        if counter >= settings.etoro_reject_threshold:
            self._suspended_until[key] = datetime.now(timezone.utc) + timedelta(
                seconds=settings.etoro_reject_backoff_seconds
            )
            logger.warning(
                "eToro rejected %s x%d for user %s — suspending symbol for %ds: %s",
                symbol, counter, user_id, settings.etoro_reject_backoff_seconds, message,
            )
        else:
            logger.warning(
                "eToro rejection #%d for %s (user %s): %s",
                counter, symbol, user_id, message,
            )

    def _clear_rejections(self, user_id: str, symbol: str) -> None:
        key = (user_id, symbol)
        self._reject_counters.pop(key, None)
        self._suspended_until.pop(key, None)

    async def _build_portfolio_snapshot(
        self, user_id: str, demo: Optional[bool] = None
    ) -> PortfolioSnapshot:
        """Capture the authoritative eToro state for a user (balance + positions).

        eToro is the source of truth for both money and open positions. Entry
        decisions never guess from local memory: if any piece is unreadable,
        ``has_error`` is set and the caller must skip opening new positions.
        """
        if demo is None:
            demo = settings.use_demo_account

        error = None
        # Reuse the positions fetched during sync_positions_from_etoro (which
        # runs right before this in run_trading_cycle) to avoid a second call
        # to eToro per user per cycle. If that fetch failed, cache is absent and
        # we retry here.
        positions = self._etoro_positions_by_user.get(user_id)
        if positions is None:
            try:
                positions = await self._etoro_http_client.get_open_positions(
                    user_id, demo=demo
                )
                self._etoro_positions_by_user[user_id] = positions
            except Exception as e:
                error = f"get_open_positions({user_id}): {e}"
                self._last_etoro_error = error
                logger.warning("Portfolio snapshot failed for %s: %s", user_id, e)
                positions = []

        # Balance: reliable data or nothing. 0.0 on failure means the snapshot
        # is NOT trustworthy → decisions must skip, never use a fake fallback.
        available = await self._get_available_balance(user_id, demo=demo)
        if available <= 0 and error is None:
            error = f"available_balance<=0 for {user_id} (eToro unreachable/empty)"

        return PortfolioSnapshot(
            user_id=user_id,
            fetched_at=datetime.now(timezone.utc),
            available_balance=available,
            positions=positions,
            error=error,
        )

    async def sync_positions_from_etoro(
        self,
        strategies: list[StrategyConfigDTO],
        demo: Optional[bool] = None,
    ) -> int:
        """
        Reconcile the bot's local open positions with the real open positions
        in eToro for the enabled strategies.

        - Brings in positions that exist in eToro but not locally (e.g. after a
          crash/restart).
        - Marks local positions that eToro has already closed (audit trail).
        - Recomputes SL/TP using the bot's own logic (swing + R:R 2:1) on the
          current candle data.
        - Only positions whose instrument matches a symbol in an enabled
          strategy are tracked (manual positions on other symbols are ignored).

        Returns the number of positions imported/updated.
        """
        logger.info("Syncing open positions from eToro...")

        # Demo mode is config-driven (settings.use_demo_account); an explicit
        # per-call override wins when provided.
        if demo is None:
            demo = settings.use_demo_account

        # Reconcile any placement attempt left half-done by a crashed process
        # BEFORE importing/removing positions, so no real eToro position is
        # ever invisible to the bot.
        await self._reconcile_orphan_attempts()

        # This cycle's reconciliation happened right now — used by the UI to
        # report how fresh the Open Positions data is.
        self._etoro_synced_at = datetime.now(timezone.utc)

        # Map user_id -> set of instrument_ids the bot watches
        user_instruments: dict[str, set[int]] = {}
        for s in strategies:
            try:
                inst = await self._resolve_instrument_id(s.user_id, s.symbol)
                if inst is not None:
                    user_instruments.setdefault(s.user_id, set()).add(inst)
            except Exception as e:
                logger.warning("Failed to resolve %s for sync: %s", s.symbol, e)

        imported = 0
        for user_id, inst_ids in user_instruments.items():
            # Fetch open positions from eToro (Java backend filters isSettled)
            try:
                etoro_positions = await self._etoro_http_client.get_open_positions(
                    user_id, demo=demo
                )
            except Exception as e:
                logger.warning("Failed to fetch open positions for %s: %s", user_id, e)
                self._last_etoro_error = f"get_open_positions({user_id}): {e}"
                # Drop any stale cached positions so the snapshot (built right
                # after) does not treat old data as authoritative.
                self._etoro_positions_by_user.pop(user_id, None)
                continue

            # Raw authoritative view (all instruments, not only the watched ones)
            # — exposed via /bot/cycles so the UI can show real eToro positions.
            self._etoro_positions_by_user[user_id] = etoro_positions

            # Keep only positions on instruments the bot watches
            relevant = [
                p for p in etoro_positions
                if p.get("instrumentID") in inst_ids
            ]
            etoro_by_id = {
                int(p["positionID"]): p
                for p in relevant
                if p.get("positionID") is not None
            }

            current = self._open_positions.get(user_id, [])
            current_by_id = {
                int(p["position_id"]): p
                for p in current
                if p.get("position_id") is not None
            }

            # Local positions no longer open in eToro → remove (memory + DB).
            # IMPORTANT: the DB row is deleted here too. Before this fix the
            # removal only mutated the in-memory tracker, so the `open_positions`
            # table kept stale rows (memory/DB/eToro drifted apart).
            removed_ids = [
                pid for pid in current_by_id if pid not in etoro_by_id
            ]
            if removed_ids:
                logger.info(
                    "Removing %d position(s) closed in eToro for user %s: %s",
                    len(removed_ids), user_id, removed_ids,
                )
                self._open_positions[user_id] = [
                    p
                    for p in current
                    if p.get("position_id") is not None
                    and int(p["position_id"]) not in removed_ids
                ]
                for pid in removed_ids:
                    try:
                        # Keep an audit trail instead of deleting the row:
                        # status -> 'closed' + close_reason + closed_at.
                        persistence.mark_position_closed(
                            user_id, int(pid), reason="closed_in_etoro"
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to mark position %s as closed in DB: %s", pid, e
                        )

            # Bring in new positions that eToro has but we don't
            kept = self._open_positions.get(user_id, [])
            known_ids = {
                int(p["position_id"])
                for p in kept
                if p.get("position_id") is not None
            }

            for pid, ep in etoro_by_id.items():
                if pid in known_ids:
                    continue

                entry = float(ep.get("openRate") or 0)
                if entry <= 0:
                    continue

                is_buy = bool(ep.get("isBuy", False))
                raw_instrument = ep.get("instrumentID")
                if raw_instrument is None:
                    continue
                instrument_id = int(raw_instrument)
                opened_at = ep.get("openDateTime") or datetime.now(timezone.utc).isoformat()

                # Recalculate SL/TP with the bot's logic from current candles
                stop_loss, take_profit = await self._recalculate_sl_tp(
                    user_id, instrument_id, entry, is_buy
                )

                # Fallback to eToro values if recalc fails
                if stop_loss is None:
                    sl = ep.get("stopLossRate")
                    stop_loss = float(sl) if sl is not None and float(sl) > 0 else None
                if take_profit is None:
                    tp = ep.get("takeProfitRate")
                    no_tp = ep.get("isNoTakeProfit", False)
                    take_profit = float(tp) if tp is not None and not no_tp and float(tp) > 0 else None

                # Determine the symbol for this instrument (from the strategy
                # that watches it) so risk adjustments resolve the right one.
                pos_symbol = "EUR/USD"
                for s in strategies:
                    if s.user_id == user_id:
                        try:
                            inst = await self._resolve_instrument_id(user_id, s.symbol)
                            if inst == instrument_id:
                                pos_symbol = s.symbol
                                break
                        except Exception:
                            pass

                position = {
                    "position_id": int(pid),
                    "entry_price": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "is_buy": is_buy,
                    "breakeven_applied": False,
                    "opened_at": opened_at,
                    "symbol": pos_symbol,
                    "source": "etoro_sync",
                }

                if user_id not in self._open_positions:
                    self._open_positions[user_id] = []
                self._open_positions[user_id].append(position)
                try:
                    persistence.save_position(user_id, position)
                except Exception as e:
                    logger.warning(
                        "Imported position #%s in memory but failed to persist to DB: %s",
                        pid, e,
                    )
                imported += 1
                logger.info(
                    "Imported position #%s (inst=%s, entry=%.5f) from eToro for user %s",
                    pid, instrument_id, entry, user_id,
                )

            # Mirror the DB with the reconciled memory. Upserts are idempotent,
            # so this heals any row that a transient DB failure earlier left
            # missing and guarantees DB == memory == eToro after each sync.
            for pos in self._open_positions.get(user_id, []):
                try:
                    persistence.save_position(user_id, pos)
                except Exception as e:
                    logger.warning(
                        "Failed to persist position %s after sync: %s",
                        pos.get("position_id"), e,
                    )

        if imported > 0:
            logger.info("Position reconciliation complete: %d position(s) imported", imported)
        else:
            logger.info("Position reconciliation complete: no new positions")
        return imported

    async def _recalculate_sl_tp(
        self,
        user_id: str,
        instrument_id: int,
        entry: float,
        is_buy: bool,
    ) -> tuple[Optional[float], Optional[float]]:
        """Recompute SL (ATR-based: MA200 ∓ mult×ATR14) and TP (2:1) from candles."""
        try:
            candles = await self._market_data_client.get_candles(
                user_id=user_id,
                instrument_id=instrument_id,
                interval=settings.default_candle_interval,
                count=settings.default_candle_count,
            )
            if not candles:
                return None, None

            # MA200 (último valor alineado)
            closes = [c.close for c in candles]
            ma_long = compute_sma(closes, settings.default_ma_long)
            if not ma_long:
                return None, None
            trend_ma200 = ma_long[-1]

            atr = compute_atr(candles, settings.atr_period)
            if atr is None:
                return None, None

            if is_buy:
                sl = trend_ma200 - settings.sl_atr_multiplier * atr
            else:
                sl = trend_ma200 + settings.sl_atr_multiplier * atr

            # Piso de seguridad (distancia mínima SL vs entry)
            min_sl_distance = settings.sl_min_distance_pips * 0.0001
            if abs(sl - entry) < min_sl_distance:
                if is_buy:
                    sl = entry - min_sl_distance
                else:
                    sl = entry + min_sl_distance

            # Validar dirección
            if (is_buy and sl >= entry) or (not is_buy and sl <= entry):
                return None, None

            tp = calculate_take_profit(
                entry, sl, settings.risk_reward_ratio, is_buy=is_buy
            )
            return sl, tp
        except Exception as e:
            logger.warning(
                "Failed to recalc SL/TP for user %s inst=%s: %s",
                user_id, instrument_id, e,
            )
            return None, None

    async def evaluate_strategy(self, strategy_id: str) -> dict[str, Any]:
        """Evaluate a single strategy by ID without executing any trades."""
        strategy = await self._strategies_client.get_strategy(strategy_id)
        if strategy is None:
            return {"error": f"Strategy {strategy_id} not found"}

        result = await self._evaluate_single_strategy(
            strategy=strategy,
            execute=False,
        )
        return result

    # ── Internal: User Processing ──────────────────────────────────────

    async def _process_user_strategies(
        self,
        user_id: str,
        strategies: list[StrategyConfigDTO],
        results: dict[str, Any],
    ) -> None:
        """Process all strategies for a single user.

        Entry decisions read the authoritative eToro portfolio snapshot (already
        captured at cycle start), so no local counter is kept here anymore.
        """
        for strategy in strategies:
            eval_result = await self._evaluate_single_strategy(
                strategy=strategy,
                execute=True,
                user_id=user_id,
            )
            results["evaluations"].append(eval_result)

            if eval_result.get("trade_executed"):
                results["trades"].append(eval_result)

    async def _evaluate_single_strategy(
        self,
        strategy: StrategyConfigDTO,
        execute: bool = True,
        user_id: Optional[str] = None,
        open_positions_count: int = 0,
    ) -> dict[str, Any]:
        """Evaluate a single strategy and optionally execute the trade."""
        result: dict[str, Any] = {
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "symbol": strategy.symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            uid = user_id or strategy.user_id
            now_utc = datetime.now(timezone.utc)

            # ── Global session filter (London–NY overlap) ────────────
            # Defensive per-strategy check: covers manual triggers
            # (/bot/cycle and /bot/evaluate/{id}) that bypass the root
            # check in run_trading_cycle().
            if settings.session_overlap_enabled and not is_within_session_overlap(
                now_utc,
                start=settings.session_overlap_start,
                end=settings.session_overlap_end,
                tz_name=settings.session_overlap_timezone,
            ):
                next_in = seconds_until_next_session_overlap(
                    now_utc,
                    start=settings.session_overlap_start,
                    end=settings.session_overlap_end,
                    tz_name=settings.session_overlap_timezone,
                )
                result["skipped"] = True
                result["reason"] = "Outside London–NY session overlap"
                result["next_run_seconds"] = next_in
                logger.info(
                    "Outside London–NY session overlap — skipping strategy %s "
                    "(next session in %.1fh)",
                    strategy.id, next_in / 3600,
                )
                return result

            # ── Per-symbol trading hours ────────────────────────────
            if not is_symbol_within_trading_hours(strategy.symbol, now_utc):
                next_in = symbol_seconds_until_next_window(strategy.symbol, now_utc)
                result["skipped"] = True
                result["reason"] = f"Outside {strategy.symbol} trading hours"
                result["next_run_seconds"] = next_in
                logger.info(
                    "Symbol %s outside trading hours — skipping strategy %s (next window in %.1fh)",
                    strategy.symbol, strategy.id, next_in / 3600,
                )
                return result

            # ── Per-symbol news blackout (alto riesgo) ──────────────
            try:
                events = await self._news_client.get_relevant_events_for_symbol(
                    strategy.symbol, now_utc
                )
            except Exception as e:
                logger.warning(
                    "News calendar check failed for %s: %s", strategy.symbol, e
                )
                events = []

            blackout = find_active_blackout_for_symbol(
                events,
                strategy.symbol,
                now_utc,
                before_minutes=settings.news_blackout_before_minutes,
                after_minutes=settings.news_blackout_after_minutes,
            )
            if blackout is not None:
                ev, window_start, window_end = blackout
                key = f"{ev.event_time_utc.isoformat()}|{ev.title}"
                if (
                    self._handled_blackout_key != key
                    and settings.news_blackout_protect_positions
                ):
                    await self._apply_news_blackout_protection(ev)
                    self._handled_blackout_key = key
                next_in = seconds_until(window_end, now_utc)
                result["skipped"] = True
                result["reason"] = f"News blackout: {ev.title} ({ev.country})"
                result["next_run_seconds"] = next_in
                result["blackout_event"] = {
                    "title": ev.title,
                    "country": ev.country,
                    "event_time": ev.event_time_utc.isoformat(),
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                }
                logger.info(
                    "Blackout for %s (%s) at %s — sleeping %.1f min",
                    ev.title, ev.country, ev.event_time_utc.isoformat(),
                    next_in / 60,
                )
                return result

            # ── eToro rejection backoff (cooldown) ────────────────
            # If eToro rejected this symbol N consecutive times, suspend new
            # entries for the configured window (5 min default). Risk
            # management of existing positions is NOT affected (that runs
            # separately in _check_risk_adjustments).
            suspended_remaining = self._is_symbol_suspended(uid, strategy.symbol)
            if suspended_remaining is not None:
                result["skipped"] = True
                result["reason"] = (
                    f"eToro rejection backoff for {strategy.symbol}: "
                    f"resuming in {suspended_remaining}s"
                )
                result["backoff_remaining_s"] = suspended_remaining
                logger.info(
                    "Symbol %s suspended for user %s (backoff %ds remaining)",
                    strategy.symbol, uid, suspended_remaining,
                )
                return result

            # 1. Resolve instrument ID via search
            instrument_id = await self._resolve_instrument_id(uid, strategy.symbol)
            if instrument_id is None:
                result["error"] = f"Cannot resolve symbol {strategy.symbol}"
                return result

            result["instrument_id"] = instrument_id

            # 2. Fetch candles
            candles = await self._market_data_client.get_candles(
                user_id=uid,
                instrument_id=instrument_id,
                interval=settings.default_candle_interval,
                count=settings.default_candle_count,
            )
            if not candles:
                result["error"] = "No candle data received"
                return result

            result["candles_count"] = len(candles)

            # 3. Fetch current rates
            rates = await self._market_data_client.get_rates(uid, [instrument_id])
            if not rates:
                result["error"] = "No rate data received"
                return result

            market_data = rates[0]
            result["bid"] = market_data.bid
            result["ask"] = market_data.ask

            # ── Dynamic pip size (from real candle precision) ──────
            pip_size = infer_pip_size_from_candles(candles)
            result["pip_size"] = pip_size

            # ── Spread (ask - bid) — dynamic filter (5% of SL) ────
            spread = abs(market_data.ask - market_data.bid)
            result["spread"] = spread

            # 4. Build strategy config for signal evaluation
            strategy_config = self._to_signal_config(strategy)

            # 5. Authoritative eToro portfolio snapshot (balance + positions).
            # Entries are ONLY decided against what eToro actually reports —
            # never against the local in-memory cache. If the snapshot cannot
            # be read (eToro unreachable / zero balance) → SKIP, no fallback.
            snapshot = self._portfolio_snapshot.get(uid)
            if snapshot is None:
                # Manual triggers (/bot/evaluate, /bot/cycle) that did not pass
                # through run_trading_cycle() build the snapshot lazily.
                snapshot = await self._build_portfolio_snapshot(uid)
                self._portfolio_snapshot[uid] = snapshot

            result["etoro_positions_count"] = len(snapshot.positions)
            result["etoro_snapshot_error"] = snapshot.error
            result["available_balance"] = snapshot.available_balance

            if snapshot.has_error:
                result["skipped"] = True
                result["reason"] = (
                    "No reliable eToro data (balance and/or positions) — "
                    f"skipping {strategy.symbol}. {snapshot.error or ''}"
                ).strip()
                logger.error(
                    "Skipping %s for user %s: no reliable eToro data (%s)",
                    strategy.symbol, uid, snapshot.error or "balance<=0",
                )
                return result

            available_balance = snapshot.available_balance

            # 5b. Max open positions POR ACTIVO (mismo símbolo), measured from
            # the real eToro portfolio (instrument_id match), not local memory.
            open_for_symbol = snapshot.count_for_instrument(instrument_id)
            result["open_positions_for_symbol"] = open_for_symbol

            max_pos = strategy.max_open_positions or settings.max_open_positions
            if open_for_symbol >= max_pos:
                result["skipped"] = True
                result["reason"] = (
                    f"Max positions reached for {strategy.symbol} "
                    f"({open_for_symbol}/{max_pos})"
                )
                return result

            # 6. Evaluate signal (pure function) with real available balance
            signal = evaluate_ma_strategy(
                strategy=strategy_config,
                candles=candles,
                market_data=market_data,
                account_balance=available_balance,
                open_positions_count=open_for_symbol,
                swing_lookback=settings.swing_lookback_candles,
                risk_per_trade=settings.risk_per_trade,
                max_positions=max_pos,
                crossover_window=settings.crossover_window_candles,
                risk_reward_ratio=settings.risk_reward_ratio,
                atr_period=settings.atr_period,
                max_candle_expansion_atr_mult=settings.max_candle_expansion_atr_mult,
                sl_atr_multiplier=settings.sl_atr_multiplier,
                sl_min_distance_pips=settings.sl_min_distance_pips,
                pip_size=pip_size,
            )

            result["signal"] = {
                "action": signal.action.value,
                "confidence": signal.confidence,
                "units": signal.units,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "reason": signal.reason,
                "context": signal.context,
                "order_type": signal.order_type,
                "limit_price": signal.limit_price,
            }

            # ── Spread filter: skip if spread > 5% of the SL distance ──
            if signal.action in (SignalAction.BUY, SignalAction.SELL) and signal.stop_loss:
                sl_distance = abs(signal.entry_price - signal.stop_loss)
                if sl_distance > 0:
                    spread_ratio = spread / sl_distance
                    if spread_ratio > 0.05:  # 5% of SL
                        result["skipped"] = True
                        result["reason"] = (
                            f"Spread too high: {spread:.5f} ({spread_ratio*100:.1f}% of SL "
                            f"{sl_distance:.5f}) — skipping {strategy.symbol}"
                        )
                        result["spread_ratio_of_sl"] = round(spread_ratio, 4)
                        logger.info(
                            "Spread %.5f = %.1f%% of SL %.5f for %s — skipping",
                            spread, spread_ratio * 100, sl_distance, strategy.symbol,
                        )
                        return result

            # ── Liquidity check: available balance must cover the risk ──
            if signal.action in (SignalAction.BUY, SignalAction.SELL) and signal.stop_loss:
                # Risk of this new position (in account currency)
                new_risk = available_balance * settings.risk_per_trade
                # Risk already committed by REAL eToro open positions (same
                # user). Pending limit orders don't exist in eToro yet, so they
                # naturally don't commit risk here.
                committed_risk = (
                    float(len(snapshot.positions)) * new_risk
                )
                if committed_risk + new_risk > available_balance:
                    result["skipped"] = True
                    result["reason"] = (
                        f"Insufficient liquidity: committed={committed_risk:.2f} "
                        f"+ new={new_risk:.2f} > balance={available_balance:.2f}"
                    )
                    logger.info(
                        "Insufficient liquidity for %s: committed=%.2f new=%.2f balance=%.2f",
                        strategy.symbol, committed_risk, new_risk, available_balance,
                    )
                    return result

            # 7. Execute trade if signal is actionable
            if execute and signal.action in (SignalAction.BUY, SignalAction.SELL):
                trade_result = await self._execute_trade(
                    user_id=uid,
                    instrument_id=instrument_id,
                    signal=signal,
                    symbol=strategy.symbol,
                )
                result["trade_result"] = trade_result

                position_id = trade_result.get("position_id")
                # A positive position_id from execute-smart is ALWAYS a real
                # fill in eToro — even when the response status is "error"
                # (that case means the position opened but eToro rejected the
                # SL/TP update). Such a position MUST be tracked, otherwise the
                # bot ignores real money exposure until the next cycle sync.
                opened_real = (
                    position_id is not None
                    and str(position_id).lstrip("-").isdigit()
                    and int(position_id) > 0
                )
                result["trade_executed"] = opened_real

                if opened_real:
                    # Track the position in memory + DB (limit orders are
                    # pending until filled — flagged so the news blackout can
                    # cancel them).
                    self._track_position(
                        user_id=uid,
                        position_id=int(position_id),
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        is_buy=signal.action == SignalAction.BUY,
                        order_type=signal.order_type,
                        units=signal.units,
                        symbol=strategy.symbol,
                        client_order_ref=trade_result.get("client_order_ref"),
                    )
                    # Reflect the new position in the in-memory eToro snapshot
                    # so a second strategy on the same instrument in this same
                    # cycle does not double-open (snapshot is otherwise frozen
                    # at cycle start).
                    snap = self._portfolio_snapshot.get(uid)
                    if snap is not None:
                        snap.positions.append({
                            "instrumentID": instrument_id,
                            "positionID": int(position_id),
                            "isBuy": signal.action == SignalAction.BUY,
                        })
                    if not trade_result.get("success"):
                        # Position opened but SL/TP was rejected — surface it,
                        # and treat it as a successful open for the cooldown
                        # (it is not a rejection of the order itself).
                        result["sl_tp_warning"] = trade_result.get("message", "")
                        logger.warning(
                            "Position %s opened in eToro but SL/TP failed for %s: %s",
                            position_id, strategy.symbol,
                            trade_result.get("message", ""),
                        )
                else:
                    logger.warning(
                        "Trade NOT tracked for user %s: success=%s position_id=%s raw=%s",
                        uid,
                        trade_result.get("success"),
                        position_id,
                        trade_result.get("raw_response"),
                    )

                # Rejection cooldown: only deliberate refusals by eToro count
                # (no position id / invalid id / HTTP failure). A position that
                # DID open (even with SL/TP trouble) clears the counter.
                if opened_real or trade_result.get("success"):
                    self._clear_rejections(uid, strategy.symbol)
                else:
                    self._register_rejection(
                        uid, strategy.symbol,
                        trade_result.get("message", "eToro rejected order"),
                    )
            else:
                result["trade_executed"] = False

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error evaluating strategy %s: %s", strategy.id, e)
            result["error"] = f"HTTP error: {e.response.status_code} {e.response.text}"
        except Exception as e:
            logger.exception("Error evaluating strategy %s", strategy.id)
            result["error"] = str(e)

        return result

    # ── Internal: Trade Execution ──────────────────────────────────────

    async def _execute_trade(
        self,
        user_id: str,
        instrument_id: int,
        signal: Signal,
        symbol: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a trade via the Java backend.

        Atomicity window: a `position_attempts` row is reserved (status
        'placing') BEFORE calling eToro and resolved (open/failed) AFTER. If
        the process dies in between, the orphan reconciliation at the next
        sync asks eToro whether the position actually exists.
        """
        client_order_ref = str(uuid.uuid4())
        payload = {
            "userId": user_id,
            "instrumentId": instrument_id,
            "isBuy": signal.action == SignalAction.BUY,
            "units": signal.units,
            "leverage": settings.default_leverage,
            "stopLoss": signal.stop_loss,
            "takeProfit": signal.take_profit,
            "breakEvenTrigger": settings.break_even_ratio,
            "orderType": signal.order_type,
            "limitPrice": signal.limit_price,
            "demo": settings.use_demo_account,
            "clientOrderRef": client_order_ref,
        }

        # 1. Reserve the attempt before touching eToro (atomic reservation).
        try:
            persistence.create_position_attempt(
                user_id,
                client_order_ref,
                symbol=symbol,
                instrument_id=instrument_id,
                is_buy=signal.action == SignalAction.BUY,
                units=signal.units,
                request_json=payload,
            )
        except Exception as e:
            logger.warning("Failed to record position attempt %s: %s", client_order_ref, e)

        # 2. Call execute-smart. Any HTTP-level failure is still recorded as a
        # failed attempt (and counts toward the rejection cooldown).
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self._base_url}/orders/execute-smart",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error("execute-smart failed for %s: %s", instrument_id, e)
            try:
                persistence.resolve_position_attempt(
                    client_order_ref, status="failed", error=f"http_error: {e}"
                )
            except Exception:
                pass
            return {
                "success": False,
                "position_id": None,
                "message": f"execute-smart HTTP error: {e}",
                "demo": settings.use_demo_account,
                "raw_response": None,
                "client_order_ref": client_order_ref,
                "rejected": True,
            }

        logger.info(
            "execute-smart response for instrument %d: status=%s positionId=%s message=%s",
            instrument_id,
            data.get("status"),
            data.get("positionId"),
            data.get("message", ""),
        )

        position_id = data.get("positionId")
        success = data.get("status") == "success"

        # eToro never returns 0/negative IDs for a real position.  Guard so a
        # silently-rejected order (HTTP 200 with an error body) is not mistaken
        # for a successful fill.
        if position_id is not None:
            try:
                pid = int(position_id)
                if pid <= 0:
                    logger.warning(
                        "execute-smart returned invalid position id %s (order rejected by eToro)",
                        position_id,
                    )
                    try:
                        persistence.resolve_position_attempt(
                            client_order_ref, status="failed",
                            response_json=data, error="invalid position id",
                        )
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "position_id": None,
                        "message": data.get("message", "Order rejected by eToro (invalid position id)"),
                        "demo": data.get("demo", settings.use_demo_account),
                        "raw_response": data.get("rawResponse"),
                        "client_order_ref": client_order_ref,
                        "rejected": True,
                    }
            except (TypeError, ValueError):
                logger.warning(
                    "execute-smart returned non-numeric position id %s — treating as failure",
                    position_id,
                )
                try:
                    persistence.resolve_position_attempt(
                        client_order_ref, status="failed",
                        response_json=data, error="non-numeric position id",
                    )
                except Exception:
                    pass
                return {
                    "success": False,
                    "position_id": None,
                    "message": data.get("message", "Order rejected (non-numeric position id)"),
                    "demo": data.get("demo", settings.use_demo_account),
                    "raw_response": data.get("rawResponse"),
                    "client_order_ref": client_order_ref,
                    "rejected": True,
                }

        # 3. Finalize the attempt. When eToro DID open the position but the
        # response reports `error` (SL/TP rejected AFTER a successful open), the
        # positionId is still a positive real value — resolve the attempt as
        # 'open' and let the caller track the position. Only true rejections
        # (no id) are recorded as 'rejected'/'failed'.
        attempt_status = (
            "open"
            if position_id is not None and int(position_id) > 0
            else "rejected"
        )
        try:
            persistence.resolve_position_attempt(
                client_order_ref, status=attempt_status,
                position_id=int(position_id) if position_id is not None else None,
                response_json=data,
                error=None if success else data.get("message"),
            )
        except Exception as e:
            logger.warning("Failed to resolve position attempt %s: %s", client_order_ref, e)

        return {
            "success": success,
            "position_id": position_id,
            "message": data.get("message", ""),
            "demo": data.get("demo", settings.use_demo_account),
            "raw_response": data.get("rawResponse"),
            "client_order_ref": client_order_ref,
            # True rejection = eToro refused the OPEN itself (no real position
            # id). When position_id>0 but status=error, eToro DID open and only
            # the SL/TP update failed → NOT a rejection.
            "rejected": not success and (
                position_id is None or int(position_id) <= 0
            ),
        }

    async def _resolve_instrument_id(
        self,
        user_id: str,
        symbol: str,
    ) -> Optional[int]:
        """Resolve an eToro instrument ID from a symbol.

        Uses the shared ``SymbolResolver`` (alias map + cached catalogue) when
        available; otherwise falls back to the old exact-match logic against
        the full instrument universe.
        """
        # Preferred path: shared resolver (consistent with the chart endpoint)
        if self.symbol_resolver is not None:
            resolved = await self.symbol_resolver.resolve(user_id, symbol)
            if resolved is not None:
                return resolved
            logger.warning("Could not resolve symbol %s via shared resolver", symbol)
            return None

        # Fallback: direct exact-match logic (kept for robustness)
        symbol_lower = symbol.lower().replace("/", "")
        try:
            result = await self._etoro_http_client.search_instruments(
                user_id=user_id,
                query=symbol,
                fields="instrumentId,internalSymbolFull,displayname",
            )
            instruments = (
                result.get("instrumentDisplayDatas")
                or result.get("InstrumentDisplayDatas")
                or result.get("items")
                or result.get("Items")
                or result.get("Instruments")
                or result.get("instruments")
                or []
            )
            if isinstance(instruments, dict):
                instruments = [instruments]

            for inst in instruments:
                inst_id = inst.get("instrumentId") or inst.get("instrumentID") or inst.get("InstrumentID")
                symbol_full = (
                    inst.get("symbolFull")
                    or inst.get("SymbolFull")
                    or inst.get("internalSymbolFull")
                    or inst.get("InternalSymbolFull")
                    or ""
                )
                display_name = (
                    inst.get("instrumentDisplayName")
                    or inst.get("InstrumentDisplayName")
                    or inst.get("displayname")
                    or inst.get("DisplayName")
                    or ""
                )
                if inst_id is None:
                    continue
                full = str(symbol_full).lower().replace("/", "")
                display = str(display_name).lower().replace("/", "")
                if full == symbol_lower or display == symbol_lower:
                    return int(inst_id)

            logger.warning("Could not resolve instrument ID for symbol %s", symbol)
            return None
        except Exception as e:
            logger.error("Failed to resolve instrument ID for %s: %s", symbol, e)
            return None

    # ── Internal: Position Tracking ────────────────────────────────────

    def _track_position(
        self,
        user_id: str,
        position_id: int,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        is_buy: bool,
        order_type: str = "market",
        units: float = 0.0,
        symbol: str = "EUR/USD",
        client_order_ref: Optional[str] = None,
    ) -> None:
        """Track an open position (or pending limit order) in memory."""
        # Never track phantom positions: eToro never returns 0/negative IDs
        # for a valid order.
        if position_id is None or int(position_id) <= 0:
            logger.warning(
                "Refusing to track phantom position id=%s for user %s",
                position_id, user_id,
            )
            return

        if user_id not in self._open_positions:
            self._open_positions[user_id] = []

        # Limit orders are PENDING (not open positions) until filled —
        # flagged so the news blackout can cancel them and so they are not
        # counted as open positions for the max-positions check.
        is_pending = order_type == "limit"

        position = {
            "position_id": position_id,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "is_buy": is_buy,
            "breakeven_applied": False,
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            # Risk state machine fields
            "state": 0,
            "sl_original": stop_loss,
            "tp_fixed": take_profit,
            "highest_price": None,
            "lowest_price": None,
            "spread_real": None,
            # Order metadata
            "order_type": order_type,
            "units": units,
            "is_pending_order": is_pending,
            "client_order_ref": client_order_ref,
        }
        self._open_positions[user_id].append(position)

        # Persist to database. The in-memory entry is kept even if this write
        # fails (e.g. transient Supabase connection issue); the next eToro
        # reconciliation mirrors the DB from memory so it self-heals.
        try:
            persistence.save_position(user_id, position)
        except Exception as e:
            logger.warning(
                "Tracked position %s in memory but failed to persist to DB: %s",
                position_id, e,
            )

    async def _check_risk_adjustments(
        self,
        results: dict[str, Any],
    ) -> None:
        """
        Check all open positions through the transversal risk module.

        For each open position, delegate to PositionRiskManager which:
        - Reads currentRate from the broker
        - Detects milestones (Hito 1 breakeven, Hito 2 secured + trailing)
        - Executes SL/TP updates against eToro (with retry)
        - Only after broker confirmation updates the local state
        """
        for user_id, positions in list(self._open_positions.items()):
            for pos in positions:
                position_id = pos.get("position_id")
                if position_id is None:
                    continue
                try:
                    state = PositionRiskState(
                        position_id=int(position_id),
                        user_id=user_id,
                        entry_price=pos["entry_price"],
                        sl_original=pos.get("sl_original") or pos["stop_loss"],
                        tp_fixed=pos.get("tp_fixed"),
                        is_buy=pos["is_buy"],
                        state=pos.get("state", 0),
                        highest_price=pos.get("highest_price"),
                        lowest_price=pos.get("lowest_price"),
                        sl_current=pos.get("stop_loss"),
                        spread_real=pos.get("spread_real"),
                    )

                    instrument_id = await self._resolve_instrument_id(
                        user_id, self._symbol_for_position(pos)
                    )
                    if instrument_id is None:
                        continue

                    decision = await self._risk_manager.manage_position(
                        position=state,
                        instrument_id=instrument_id,
                    )
                    if decision is None:
                        continue

                    # Broker confirmed → update local state + persistence
                    new_sl = decision.new_stop_loss
                    pos["stop_loss"] = new_sl if new_sl is not None else pos.get("stop_loss")
                    pos["state"] = decision.new_state
                    if decision.spread_real is not None:
                        pos["spread_real"] = decision.spread_real
                    if decision.highest_price is not None:
                        pos["highest_price"] = decision.highest_price
                    if decision.lowest_price is not None:
                        pos["lowest_price"] = decision.lowest_price
                    pos["breakeven_applied"] = decision.new_state >= 1

                    persistence.update_position_state(
                        user_id=user_id,
                        position_id=int(position_id),
                        state=decision.new_state,
                        stop_loss=pos["stop_loss"],
                        take_profit=pos.get("take_profit"),
                        highest_price=pos.get("highest_price"),
                        lowest_price=pos.get("lowest_price"),
                        spread_real=pos.get("spread_real"),
                    )

                    results["adjustments"].append({
                        "position_id": position_id,
                        "action": "risk_state",
                        "new_state": decision.new_state,
                        "new_stop_loss": pos["stop_loss"],
                        "reason": decision.reason,
                        "user_id": user_id,
                    })
                    logger.info(
                        "Risk state %d applied to position %d for user %s: %s",
                        decision.new_state, position_id, user_id, decision.reason,
                    )

                except Exception as e:
                    logger.warning(
                        "Failed to check risk for position %d: %s",
                        position_id, e,
                    )

    def _symbol_for_position(self, position: dict[str, Any]) -> str:
        """Best-effort symbol lookup for a position (defaults to EUR/USD)."""
        return position.get("symbol") or "EUR/USD"

    # ── Internal: News Blackout Protection ─────────────────────────────

    async def _apply_news_blackout_protection(self, event: NewsEvent) -> None:
        """
        Execute the INICIO PAUSA policy before a High-impact news event:
        1. Cancel pending limit orders.
        2. Move open positions in profit to breakeven (or close 50% when
           configured).
        Positions in loss keep their original stop loss.
        """
        logger.info(
            "Applying news blackout protection for %s (%s) at %s",
            event.title, event.country, event.event_time_utc.isoformat(),
        )
        for user_id, positions in list(self._open_positions.items()):
            # 1. Cancel pending limit orders
            pending = [p for p in positions if p.get("is_pending_order")]
            for pos in pending:
                order_id = pos.get("position_id")
                if order_id is None:
                    continue
                try:
                    await self._etoro_http_client.cancel_order(
                        user_id, int(order_id)
                    )
                    logger.info("Cancelled pending order %s for user %s", order_id, user_id)
                except Exception as e:
                    logger.warning("Failed to cancel pending order %s: %s", order_id, e)
                # Remove from tracker (order no longer exists) regardless
                self._open_positions[user_id] = [
                    p for p in self._open_positions.get(user_id, [])
                    if p.get("position_id") != pos.get("position_id")
                ]
                persistence.delete_position(user_id, int(order_id))

            # 2. Protect open (real) positions — breakeven if in profit
            if not settings.news_blackout_protect_positions:
                continue
            current_positions = self._open_positions.get(user_id, [])
            for pos in current_positions:
                if pos.get("is_pending_order"):
                    continue
                try:
                    await self._protect_position_before_news(user_id, pos)
                except Exception as e:
                    logger.warning(
                        "Failed to protect position %s for user %s: %s",
                        pos.get("position_id"), user_id, e,
                    )

    async def _protect_position_before_news(
        self,
        user_id: str,
        pos: dict[str, Any],
    ) -> None:
        """Move an open position to breakeven if it is in profit (R >= 0)."""
        instrument_id = await self._resolve_instrument_id(
            user_id, self._symbol_for_position(pos)
        )
        if instrument_id is None:
            return

        rates = await self._market_data_client.get_rates(user_id, [instrument_id])
        if not rates:
            logger.warning("No rates available to protect position %s", pos.get("position_id"))
            return
        r0 = rates[0]

        position_state = PositionRiskState(
            position_id=int(pos["position_id"]),
            user_id=user_id,
            entry_price=pos["entry_price"],
            sl_original=pos.get("sl_original") or pos["stop_loss"],
            tp_fixed=pos.get("tp_fixed"),
            is_buy=pos["is_buy"],
            state=pos.get("state", 0),
            highest_price=pos.get("highest_price"),
            lowest_price=pos.get("lowest_price"),
            sl_current=pos.get("stop_loss"),
            spread_real=pos.get("spread_real"),
        )

        current_price = r0.bid if pos["is_buy"] else r0.ask
        risk = abs(position_state.entry_price - position_state.sl_original)
        if risk <= 0:
            return

        r = compute_risk_from_price(position_state, current_price)
        if r < 0:
            logger.info(
                "Position %s in loss (R=%.3f) — keeping original SL",
                pos["position_id"], r,
            )
            return

        # In profit → move SL to breakeven (+ spread)
        spread = abs(r0.ask - r0.bid)
        if pos["is_buy"]:
            be_sl = round(pos["entry_price"] + spread, 5)
        else:
            be_sl = round(pos["entry_price"] - spread, 5)

        try:
            await self._etoro_http_client.update_stop_loss(
                user_id, int(pos["position_id"]), be_sl
            )
            pos["stop_loss"] = be_sl
            pos["breakeven_applied"] = True
            pos["spread_real"] = spread
            persistence.update_position_state(
                user_id=user_id,
                position_id=int(pos["position_id"]),
                state=max(pos.get("state", 0), 1),
                stop_loss=be_sl,
                take_profit=pos.get("take_profit"),
                highest_price=pos.get("highest_price"),
                lowest_price=pos.get("lowest_price"),
                spread_real=spread,
            )
            logger.info(
                "News protection: position %s moved to breakeven SL=%.5f (R=%.3f)",
                pos["position_id"], be_sl, r,
            )
        except Exception as e:
            logger.warning("Failed to move position %s to breakeven: %s", pos["position_id"], e)

    async def _check_reopen_spread(self) -> bool:
        """
        After a news blackout, confirm the EUR/USD spread has returned to
        normal before resuming trading.  Returns True when the spread is
        within the configured maximum (in pips).
        """
        try:
            instrument_id = await self._resolve_instrument_id(
                "00000000-0000-0000-0000-000000000000", "EUR/USD"
            )
            if instrument_id is None:
                return True  # cannot verify → allow trading
            rates = await self._market_data_client.get_rates(
                "00000000-0000-0000-0000-000000000000", [instrument_id]
            )
            if not rates:
                return True  # cannot verify → allow trading (fail-open)
            r0 = rates[0]
            spread = abs(r0.ask - r0.bid)
            max_spread = settings.news_reopen_max_spread_pips * 0.0001
            normal = spread <= max_spread
            logger.info(
                "Reopen spread check: spread=%.5f pips=%.1f max=%.1f → %s",
                spread, spread / 0.0001,
                settings.news_reopen_max_spread_pips,
                "normal" if normal else "still wide",
            )
            return normal
        except Exception as e:
            logger.warning("Failed to check reopen spread: %s", e)
            return True  # fail-open on error

    # ── Internal: Portfolio Balance ────────────────────────────────────

    async def _get_available_balance(self, user_id: str, demo: Optional[bool] = None) -> float:
        """
        Fetch the available cash balance from the eToro DEMO portfolio.

        The real portfolio (demo=False) often returns 403 InsufficientPermissions
        unless the user has explicitly granted the token access, so we default to
        the DEMO account.  We read ``clientPortfolio.credit`` which is the real
        available cash returned by eToro.

        Returns 0.0 (NOT the old hardcoded 10_000 fallback) if the balance cannot
        be read — the scheduler will skip trades with an explicit reason instead
        of silently sizing positions against a fake balance.
        """
        if demo is None:
            demo = settings.use_demo_account

        try:
            portfolio = await self._etoro_http_client.get_portfolio(
                user_id, demo=demo
            )

            # Real eToro portfolio response:
            #   { "clientPortfolio": { "credit": 1798.14, "bonusCredit": 0.0, "positions": [...] } }
            cp = (
                portfolio.get("clientPortfolio")
                or portfolio.get("ClientPortfolio")
                or portfolio
            )
            available = (
                cp.get("credit")
                or cp.get("Credit")
                or cp.get("availableCash")
                or cp.get("AvailableCash")
                or 0
            )
            balance = float(available)

            if balance <= 0:
                logger.error(
                    "Available balance is %f for user %s — refusing to use a fake fallback",
                    balance,
                    user_id,
                )
                return 0.0

            logger.info("Available balance for user %s: %.2f", user_id, balance)
            return balance
        except Exception as e:
            logger.error("Failed to fetch portfolio for %s: %s", user_id, e)
            return 0.0

    # ── Internal: Trading Hours ─────────────────────────────────────────

    @staticmethod
    def _is_within_trading_hours() -> bool:
        """
        Check if the current time is within EUR/USD trading hours.
        FX market opens Sunday 5pm ET and closes Friday 5pm ET.
        """
        now_utc = datetime.now(timezone.utc)

        if HAS_PYTZ and pytz is not None:
            try:
                eastern = pytz.timezone(settings.trading_timezone)
                now_et = now_utc.astimezone(eastern)
            except Exception:
                now_et = now_utc
        else:
            # Fallback: approximate ET as UTC-5 (or UTC-4 during EDT)
            now_et = now_utc

        weekday = now_et.weekday()  # Monday=0, Sunday=6
        hour = now_et.hour
        minute = now_et.minute
        total_minutes = hour * 60 + minute
        market_open_minutes = 17 * 60  # 5:00 PM = 17:00

        if weekday == 6:  # Sunday
            # Open from 5pm ET
            return total_minutes >= market_open_minutes
        elif weekday == 4:  # Friday
            # Close at 5pm ET
            return total_minutes < market_open_minutes
        elif weekday == 5:  # Saturday
            # Closed all day
            return False
        else:
            # Monday-Thursday: 24 hours
            return True

    @staticmethod
    def _seconds_until_next_trading_window() -> int:
        """
        Calculate the number of seconds until the next trading window opens.

        The FX market opens Sunday 5pm ET.  This is used by the scheduler to
        sleep for the whole weekend instead of waking up every interval.
        """
        now_utc = datetime.now(timezone.utc)

        if HAS_PYTZ and pytz is not None:
            try:
                eastern = pytz.timezone(settings.trading_timezone)
                now_et = now_utc.astimezone(eastern)
            except Exception:
                now_et = now_utc
        else:
            # Fallback: approximate ET as UTC-5 (or UTC-4 during EDT)
            now_et = now_utc

        market_open_minutes = 17 * 60  # 5:00 PM ET

        # Build the next market-open datetime in ET wall-clock time.
        # ``now_et`` is tz-aware here, so strip tzinfo to build a naive wall-clock
        # datetime and then re-attach the ET zone with pytz.localize() (which
        # REQUIRES a naive datetime; localizing an aware one corrupts the offset).
        today_local_naive = now_et.replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
        days_until_sunday = (6 - today_local_naive.weekday()) % 7  # days until next Sunday
        next_sunday_naive = today_local_naive + timedelta(days=days_until_sunday)

        if days_until_sunday == 0 and now_et.hour * 60 + now_et.minute < market_open_minutes:
            # It is Sunday before 5pm ET — market opens today at 5pm ET.
            next_open_naive = next_sunday_naive.replace(hour=17, minute=0, second=0, microsecond=0)
        elif days_until_sunday == 0 and now_et.hour * 60 + now_et.minute >= market_open_minutes:
            # Sunday after 5pm ET — market is open; should not be called, but guard anyway.
            next_open_naive = next_sunday_naive.replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=7)
        else:
            # Any other weekday outside hours (Friday after 5pm, all Saturday, etc.)
            next_open_naive = next_sunday_naive.replace(hour=17, minute=0, second=0, microsecond=0)

        # Attach the ET timezone so the subtraction is DST-safe.
        try:
            if HAS_PYTZ and pytz is not None:
                et_timezone = pytz.timezone(settings.trading_timezone)
                next_open_et = et_timezone.localize(next_open_naive)  # naive → aware ET
            else:
                # Fallback: assume a fixed UTC-5 offset when pytz is unavailable.
                next_open_et = next_open_naive.replace(tzinfo=timezone(timedelta(hours=-5)))
        except Exception:
            # Last resort: treat the naive local time as UTC.
            next_open_et = next_open_naive.replace(tzinfo=timezone.utc)

        delta = next_open_et - now_utc
        seconds = int(delta.total_seconds())
        return max(seconds, 60)  # never return less than 1 minute

    def _to_signal_config(self, dto: StrategyConfigDTO) -> StrategyConfig:
        """Convert a StrategyConfigDTO to the signals.StrategyConfig used by the pure functions."""
        return StrategyConfig(
            id=dto.id,
            user_id=dto.user_id,
            symbol=dto.symbol,
            enabled=dto.enabled,
            ma_short_period=settings.default_ma_short,
            ma_long_period=settings.default_ma_long,
            max_position_size=dto.max_position_size,
            max_open_positions=dto.max_open_positions,
            stop_loss=dto.stop_loss,
            take_profit=dto.take_profit,
            break_even_trigger=dto.break_even_trigger,
            use_ml=dto.use_ml,
            ml_strategy_code=dto.ml_strategy_code,
        )