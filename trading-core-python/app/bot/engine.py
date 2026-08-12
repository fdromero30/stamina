"""Deterministic trading engine - the core orchestrator."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

from app.bot import persistence
from app.bot.news_calendar import (
    NewsCalendarClient,
    NewsEvent,
    find_active_blackout,
    is_time_for_reopen_spread_check,
    seconds_until,
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
        """Execute a single trading cycle for all enabled strategies."""
        logger.info("Starting trading cycle...")

        # Check if we're within EUR/USD trading hours (Sun 5pm ET - Fri 5pm ET)
        if not self._is_within_trading_hours():
            next_in = self._seconds_until_next_trading_window()
            logger.info(
                "Outside EUR/USD trading hours, skipping cycle (next window in %.1f hours)",
                next_in / 3600,
            )
            return {
                "skipped": True,
                "reason": "Outside trading hours",
                "next_run_seconds": next_in,
            }

        now_utc = datetime.now(timezone.utc)

        # ── News blackout (alto riesgo) ───────────────────────────────
        # Consulta el calendario económico (caché primero; HTTP solo en
        # arranque, long-sleep y prefetch −5min).  Si estamos dentro de un
        # blackout High de EUR/USD, el bot se detiene y duerme hasta el
        # final de la ventana (evento + 30 min).
        try:
            events = await self._news_client.get_relevant_events(now_utc)
        except Exception as e:
            logger.warning("News calendar check failed: %s", e)
            events = []

        blackout = find_active_blackout(
            events,
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
            logger.info(
                "News blackout: %s (%s) at %s — sleeping %.1f min until reopen",
                ev.title,
                ev.country,
                ev.event_time_utc.isoformat(),
                next_in / 60,
            )
            return {
                "skipped": True,
                "reason": f"News blackout: {ev.title} ({ev.country})",
                "next_run_seconds": next_in,
                "blackout_event": {
                    "title": ev.title,
                    "country": ev.country,
                    "event_time": ev.event_time_utc.isoformat(),
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                },
            }

        # ── Reapertura: verificar spread antes de reanudar ────────────
        if is_time_for_reopen_spread_check(
            events,
            now_utc,
            after_minutes=settings.news_blackout_after_minutes,
            grace_minutes=settings.news_reopen_spread_check_minutes,
        ):
            spread_normal = await self._check_reopen_spread()
            if not spread_normal:
                self._reopen_spread_retries += 1
                logger.warning(
                    "Spread still wide after news (retry %d) — skipping cycle",
                    self._reopen_spread_retries,
                )
                return {
                    "skipped": True,
                    "reason": "Spread above news_reopen_max_spread_pips after news blackout",
                    "next_run_seconds": settings.trading_interval_seconds,
                }
            self._reopen_spread_retries = 0

        results: dict[str, Any] = {
            "evaluations": [],
            "trades": [],
            "adjustments": [],
        }

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
                default_strategy = StrategyConfigDTO(
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
                enabled = [default_strategy]
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
        - Removes local positions that eToro has already closed.
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
                continue

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

            # Local positions no longer open in eToro → remove
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

                position = {
                    "position_id": int(pid),
                    "entry_price": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "is_buy": is_buy,
                    "breakeven_applied": False,
                    "opened_at": opened_at,
                    "source": "etoro_sync",
                }

                if user_id not in self._open_positions:
                    self._open_positions[user_id] = []
                self._open_positions[user_id].append(position)
                persistence.save_position(user_id, position)
                imported += 1
                logger.info(
                    "Imported position #%s (inst=%s, entry=%.5f) from eToro for user %s",
                    pid, instrument_id, entry, user_id,
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
        """Recompute SL (swing) and TP (2:1 risk:reward) from current candles."""
        try:
            candles = await self._market_data_client.get_candles(
                user_id=user_id,
                instrument_id=instrument_id,
                interval=settings.default_candle_interval,
                count=settings.default_candle_count,
            )
            if not candles:
                return None, None

            if is_buy:
                sl = find_swing_low(candles, settings.swing_lookback_candles)
            else:
                sl = find_swing_high(candles, settings.swing_lookback_candles)

            if sl is None:
                return None, None
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
        """Process all strategies for a single user."""
        open_positions = self._open_positions.get(user_id, [])
        open_count = len(open_positions)

        for strategy in strategies:
            eval_result = await self._evaluate_single_strategy(
                strategy=strategy,
                execute=True,
                user_id=user_id,
                open_positions_count=open_count,
            )
            results["evaluations"].append(eval_result)

            if eval_result.get("trade_executed"):
                results["trades"].append(eval_result)
                open_count += 1

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

            # 4. Build strategy config for signal evaluation
            strategy_config = self._to_signal_config(strategy)

            # 5. Fetch available balance for position sizing
            available_balance = await self._get_available_balance(uid)
            result["available_balance"] = available_balance

            # 6. Evaluate signal (pure function) with real available balance
            signal = evaluate_ma_strategy(
                strategy=strategy_config,
                candles=candles,
                market_data=market_data,
                account_balance=available_balance,
                open_positions_count=open_positions_count,
                swing_lookback=settings.swing_lookback_candles,
                risk_per_trade=settings.risk_per_trade,
                max_positions=settings.max_open_positions,
                crossover_window=settings.crossover_window_candles,
                risk_reward_ratio=settings.risk_reward_ratio,
                atr_period=settings.atr_period,
                max_candle_expansion_atr_mult=settings.max_candle_expansion_atr_mult,
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

            # 7. Execute trade if signal is actionable
            if execute and signal.action in (SignalAction.BUY, SignalAction.SELL):
                trade_result = await self._execute_trade(
                    user_id=uid,
                    instrument_id=instrument_id,
                    signal=signal,
                )
                result["trade_executed"] = trade_result.get("success", False)
                result["trade_result"] = trade_result

                if trade_result.get("success") and trade_result.get("position_id"):
                    # Track the position in memory (limit orders are pending
                    # until filled — flagged so the news blackout can cancel them)
                    self._track_position(
                        user_id=uid,
                        position_id=trade_result["position_id"],
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        is_buy=signal.action == SignalAction.BUY,
                        order_type=signal.order_type,
                        units=signal.units,
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
    ) -> dict[str, Any]:
        """Execute a trade via the Java backend."""
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
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}/orders/execute-smart",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return {
            "success": data.get("status") == "success",
            "position_id": data.get("positionId"),
            "message": data.get("message", ""),
            "demo": data.get("demo", settings.use_demo_account),
            "raw_response": data.get("rawResponse"),
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
    ) -> None:
        """Track an open position (or pending limit order) in memory."""
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
        }
        self._open_positions[user_id].append(position)

        # Persist to database
        persistence.save_position(user_id, position)

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
        # Positions do not store the symbol directly today; the strategy
        # symbol is EUR/USD in the default setup.  For custom strategies the
        # engine already resolved the instrument at trade time.
        return "EUR/USD"

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