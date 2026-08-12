"""
PositionRiskManager — orchestrates the risk state machine for open positions.

This manager is strategy-agnostic: it receives a `PositionRiskState`, fetches
market data (current rate, candle high/low, ATR), evaluates the pure state
machine, and executes any resulting decision against the broker.

Key behaviours:
- Idempotent: if the broker already has the requested SL/TP, nothing is sent.
- Retry: if the broker rejects an SL update, retry once after a short delay.
- Persist only after broker confirmation: the local state always reflects
  what eToro actually accepted.
"""

import asyncio
import logging
from typing import Any, Optional

from app.settings import settings

from .models import (
    MarketSnapshot,
    PositionRiskState,
    RiskDecision,
    RiskManagementConfig,
)
from .state_machine import evaluate

logger = logging.getLogger(__name__)


class PositionRiskManager:
    """Transversal risk manager — usable by any strategy's positions."""

    def __init__(
        self,
        etoro_http_client: Any,
        market_data_client: Any,
        config_provider: Optional[Any] = None,
        default_config: Optional[RiskManagementConfig] = None,
        candle_interval: str = "5m",
        candle_count: int = 300,
        max_tp_far_retries: int = 2,
    ) -> None:
        """
        Args:
            etoro_http_client: client exposing get_open_positions(),
                update_stop_loss(), update_take_profit().
            market_data_client: client exposing get_candles(user_id,
                instrument_id, interval, count).
            config_provider: optional callable position -> RiskManagementConfig.
            default_config: fallback config when config_provider is absent/None.
            candle_interval: interval used to fetch candles for high/low/ATR.
            candle_count: number of candles to fetch for ATR computation.
        """
        self._etoro = etoro_http_client
        self._market_data = market_data_client
        self._config_provider = config_provider
        self._default_config = default_config or RiskManagementConfig()
        self._candle_interval = candle_interval
        self._candle_count = candle_count
        self._max_tp_far_retries = max_tp_far_retries

    # ── Primary entry point ────────────────────────────────────────────

    async def manage_position(
        self,
        position: PositionRiskState,
        instrument_id: int,
        current_rate: Optional[float] = None,
        candle_high: Optional[float] = None,
        candle_low: Optional[float] = None,
        atr: Optional[float] = None,
        ask: Optional[float] = None,
        bid: Optional[float] = None,
    ) -> Optional[RiskDecision]:
        """
        Evaluate and, if needed, execute the risk decision for ONE position.

        Returns the executed RiskDecision (or None if nothing was needed).
        The caller is responsible for persisting the updated position state
        AFTER this method confirms the broker accepted the change.
        """
        try:
            config = self._config_for(position)
        except Exception as e:
            logger.warning("Failed to resolve risk config for position %d: %s", position.position_id, e)
            return None

        snapshot = await self._build_snapshot(
            position, instrument_id, current_rate, candle_high, candle_low, atr, ask, bid
        )
        if snapshot is None:
            return None

        try:
            decision = evaluate(position, snapshot, config)
        except Exception as e:
            logger.error("State machine evaluation failed for %d: %s", position.position_id, e)
            return None

        if decision is None:
            return None

        executed = await self._execute_decision(position, decision, config)
        return decision if executed else None

    # ── Snapshot building ──────────────────────────────────────────────

    async def _build_snapshot(
        self,
        position: PositionRiskState,
        instrument_id: int,
        current_rate: Optional[float],
        candle_high: Optional[float],
        candle_low: Optional[float],
        atr: Optional[float],
        ask: Optional[float],
        bid: Optional[float],
    ) -> Optional[MarketSnapshot]:
        """Fetch any missing market data and construct a MarketSnapshot."""
        rate = current_rate
        high = candle_high
        low = candle_low
        atr_val = atr
        ask_val = ask
        bid_val = bid

        if rate is None:
            try:
                open_positions = await self._etoro.get_open_positions(
                    position.user_id,
                    demo=settings.use_demo_account,
                )
                for p in open_positions:
                    if int(p.get("positionID", 0)) == position.position_id:
                        cr = p.get("currentRate")
                        if cr is not None:
                            rate = float(cr)
                        break
            except Exception as e:
                logger.warning(
                    "Failed to fetch currentRate for position %d: %s",
                    position.position_id, e,
                )

        if rate is None:
            logger.warning(
                "No current rate available for position %d — skipping",
                position.position_id,
            )
            return None

        if high is None or low is None or atr_val is None:
            try:
                candles = await self._market_data.get_candles(
                    user_id=position.user_id,
                    instrument_id=instrument_id,
                    interval=self._candle_interval,
                    count=self._candle_count,
                )
                if candles:
                    completed = candles[-2] if len(candles) > 1 else candles[-1]
                    if high is None:
                        high = float(completed.high)
                    if low is None:
                        low = float(completed.low)
                    if atr_val is None:
                        atr_val = self._compute_atr_from_candles(candles)
            except Exception as e:
                logger.warning(
                    "Failed to fetch candle/ATR data for position %d: %s",
                    position.position_id, e,
                )

        # Capture the spread via market_data_client.get_rates (MarketData objects)
        if ask_val is None or bid_val is None:
            try:
                rates = await self._market_data.get_rates(position.user_id, [instrument_id])
                if rates:
                    r0 = rates[0]
                    ask_val = float(r0.ask)
                    bid_val = float(r0.bid)
            except Exception as e:
                logger.warning(
                    "Failed to fetch rates for spread (position %d): %s",
                    position.position_id, e,
                )

        return MarketSnapshot(
            current_rate=float(rate),
            candle_high=float(high) if high is not None and high > 0 else None,
            candle_low=float(low) if low is not None and low > 0 else None,
            ask=float(ask_val) if ask_val is not None else None,
            bid=float(bid_val) if bid_val is not None else None,
            atr=float(atr_val) if atr_val is not None else None,
        )

    def _compute_atr_from_candles(self, candles: list[Any]) -> Optional[float]:
        """Compute ATR(14) from a list of Candle objects (app.bot.signals.Candle)."""
        try:
            from app.bot.signals import compute_atr

            return compute_atr(candles, period=14)
        except Exception as e:
            logger.warning("Failed to compute ATR: %s", e)
            return None

    # ── Config resolution ───────────────────────────────────────────────

    def _config_for(self, position: PositionRiskState) -> RiskManagementConfig:
        """Resolve the risk config for a position (per strategy or default)."""
        if self._config_provider is not None:
            cfg = self._config_provider(position)
            if cfg is not None:
                return cfg
        return self._default_config

    # ── Decision execution (idempotent + retry) ─────────────────────────

    async def _execute_decision(
        self,
        position: PositionRiskState,
        decision: RiskDecision,
        config: RiskManagementConfig,
    ) -> bool:
        """
        Execute the decision against the broker.

        Returns True if the broker confirmed the change; False if it failed
        even after a retry (the caller must NOT update its local state).
        """
        if decision.new_stop_loss is not None:
            ok = await self._execute_stop_loss_with_retry(
                position, decision.new_stop_loss, config
            )
            if not ok:
                return False

        if decision.remove_take_profit:
            ok = await self._execute_far_tp(position, config)
            if not ok:
                logger.warning(
                    "Could not move TP to far level for position %d — keeping original TP",
                    position.position_id,
                )
                # Not fatal: the secured SL is already in place.
                # The fixed TP may still take profit at 2.0R, which is acceptable.

        return True

    async def _execute_stop_loss_with_retry(
        self,
        position: PositionRiskState,
        new_sl: float,
        config: RiskManagementConfig,
    ) -> bool:
        """Send the SL update; retry once after `sl_update_retry_seconds`."""
        if position.sl_current is not None and abs(position.sl_current - new_sl) < 1e-9:
            logger.info("SL already at %.5f for position %d — skipping", new_sl, position.position_id)
            return True

        attempts = 2  # initial + 1 retry
        for attempt in range(attempts):
            try:
                await self._etoro.update_stop_loss(
                    position.user_id, position.position_id, new_sl
                )
                logger.info(
                    "SL updated to %.5f for position %d (attempt %d)",
                    new_sl, position.position_id, attempt + 1,
                )
                return True
            except Exception as e:
                logger.warning(
                    "SL update rejected for position %d (attempt %d/%d): %s",
                    position.position_id, attempt + 1, attempts, e,
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(config.sl_update_retry_seconds)
        return False

    async def _execute_far_tp(
        self,
        position: PositionRiskState,
        config: RiskManagementConfig,
    ) -> bool:
        """
        Move the fixed TP to a far level (max_tp_far_r) so the trailing can
        scale the position.  If the far level is rejected, try a lower one.
        """
        if position.tp_fixed is None:
            return True

        risk = abs(position.entry_price - position.sl_original)
        candidates = [config.max_tp_far_r, 3.0, 2.0]
        for i, r_mult in enumerate(candidates[: self._max_tp_far_retries + 1]):
            if position.is_buy:
                far_tp = round(position.entry_price + r_mult * risk, 5)
            else:
                far_tp = round(position.entry_price - r_mult * risk, 5)

            if position.tp_fixed is not None and abs(far_tp - position.tp_fixed) < 1e-9:
                logger.info("Far TP == fixed TP for position %d — skipping", position.position_id)
                return True

            try:
                await self._etoro.update_take_profit(
                    position.user_id, position.position_id, far_tp
                )
                logger.info(
                    "TP moved to far level %.5f (%.1fR) for position %d",
                    far_tp, r_mult, position.position_id,
                )
                return True
            except Exception as e:
                logger.warning(
                    "TP update to %.5f rejected for position %d: %s",
                    far_tp, position.position_id, e,
                )
                if i < len(candidates) - 1:
                    await asyncio.sleep(1)

        return False