"""Deterministic trading engine - the core orchestrator."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

from app.bot import persistence
from app.bot.signals import (
    Signal,
    SignalAction,
    Candle,
    MarketData,
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
from app.settings import settings

logger = logging.getLogger(__name__)

# Try to import pytz for timezone support; fallback to UTC offset
try:
    import pytz
    HAS_PYTZ = True
except ImportError:
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
    ) -> None:
        self._strategies_client = strategies_client
        self._market_data_client = market_data_client
        self._etoro_http_client = etoro_http_client
        self._base_url = base_url.rstrip("/")
        # Shared symbol resolver (optional; set by main.py).  Uses the same
        # cache as the chart endpoint so symbol mapping is consistent.
        self.symbol_resolver: Optional[SymbolResolver] = None

        # In-memory tracker for open positions (per user)
        # { user_id: [ { position_id, entry_price, stop_loss, take_profit, is_buy, ... } ] }
        self._open_positions: dict[str, list[dict[str, Any]]] = {}

        # Restore persisted open positions
        self._open_positions = persistence.load_open_positions()

    @property
    def open_positions(self) -> dict[str, list[dict[str, Any]]]:
        """Return the in-memory open positions tracker (per user)."""
        return self._open_positions

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

            # 5. Check open positions for breakeven adjustments
            await self._check_breakeven_adjustments(results)

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
        demo: bool = True,
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
            current_by_id = {int(p["position_id"]): p for p in current}

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
                    p for p in current if int(p.get("position_id")) not in removed_ids
                ]

            # Bring in new positions that eToro has but we don't
            kept = self._open_positions.get(user_id, [])
            known_ids = {int(p["position_id"]) for p in kept}

            for pid, ep in etoro_by_id.items():
                if pid in known_ids:
                    continue

                entry = float(ep.get("openRate") or 0)
                if entry <= 0:
                    continue

                is_buy = bool(ep.get("isBuy", False))
                instrument_id = int(ep.get("instrumentID"))
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

            tp = calculate_take_profit(entry, sl, 2.0, is_buy=is_buy)
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
                    # Track the position in memory
                    self._track_position(
                        user_id=uid,
                        position_id=trade_result["position_id"],
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        is_buy=signal.action == SignalAction.BUY,
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
    ) -> None:
        """Track an open position in memory."""
        if user_id not in self._open_positions:
            self._open_positions[user_id] = []

        position = {
            "position_id": position_id,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "is_buy": is_buy,
            "breakeven_applied": False,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }
        self._open_positions[user_id].append(position)

        # Persist to database
        persistence.save_position(user_id, position)

    async def _check_breakeven_adjustments(
        self,
        results: dict[str, Any],
    ) -> None:
        """
        Check all open positions to see if they've reached the breakeven trigger.
        If a position has reached 1.5:1 risk:reward, move SL to breakeven.
        """
        for user_id, positions in list(self._open_positions.items()):
            for pos in positions:
                if pos.get("breakeven_applied"):
                    continue

                try:
                    # Fetch current rate to check P&L
                    portfolio = await self._etoro_http_client.get_portfolio(user_id)
                    # We'd need to check the position's current P&L here
                    # For now, use a simplified approach: check via portfolio endpoint

                    if self._should_apply_breakeven(pos, portfolio):
                        # Calculate breakeven SL
                        be_sl = calculate_breakeven_stop_loss(
                            entry_price=pos["entry_price"],
                            spread=0.0001,  # EUR/USD typical spread
                            is_buy=pos["is_buy"],
                        )

                        # Update SL via Java backend
                        async with httpx.AsyncClient(timeout=15) as client:
                            await client.put(
                                f"{self._base_url}/etoro/trading/stop-loss/{pos['position_id']}",
                                params={"userId": user_id, "stopLoss": be_sl},
                            )

                        pos["stop_loss"] = be_sl
                        pos["breakeven_applied"] = True
                        results["adjustments"].append({
                            "position_id": pos["position_id"],
                            "action": "breakeven",
                            "new_stop_loss": be_sl,
                            "user_id": user_id,
                        })

                        # Persist breakeven update to database
                        persistence.update_position_breakeven(
                            user_id=user_id,
                            position_id=pos["position_id"],
                            stop_loss=be_sl,
                        )
                        logger.info(
                            "Breakeven applied to position %d for user %s",
                            pos["position_id"],
                            user_id,
                        )

                except Exception as e:
                    logger.warning(
                        "Failed to check breakeven for position %d: %s",
                        pos.get("position_id"),
                        e,
                    )

    def _should_apply_breakeven(
        self,
        position: dict[str, Any],
        portfolio: dict[str, Any],
    ) -> bool:
        """
        Determine if a position has reached the breakeven trigger ratio.
        Simplified: checks if current price has moved enough.
        """
        # For now, return False - this needs real portfolio data to work
        # In a real implementation, we'd parse the portfolio response to find
        # the position's current P&L and compare against the risk amount
        current_price = portfolio.get("currentPrice")
        if current_price is None:
            return False

        entry = position["entry_price"]
        is_buy = position["is_buy"]

        if is_buy and current_price > entry:
            gain_ratio = (current_price - entry) / (entry - position.get("stop_loss", entry))
            return gain_ratio >= settings.break_even_ratio
        elif not is_buy and current_price < entry:
            gain_ratio = (entry - current_price) / (position.get("stop_loss", entry) - entry)
            return gain_ratio >= settings.break_even_ratio

        return False

    # ── Internal: Portfolio Balance ────────────────────────────────────

    async def _get_available_balance(self, user_id: str, demo: bool = True) -> float:
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
        try:
            if demo:
                portfolio = await self._etoro_http_client.get_demo_portfolio(user_id)
            else:
                portfolio = await self._etoro_http_client.get_portfolio(user_id)

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

        if HAS_PYTZ:
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

        if HAS_PYTZ:
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
            if HAS_PYTZ:
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

    def _to_signal_config(self, dto: StrategyConfigDTO) -> "StrategyConfig":
        """Convert a StrategyConfigDTO to the signals.StrategyConfig used by the pure functions."""
        from app.bot.signals import StrategyConfig

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