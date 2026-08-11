"""Generic data models for the transversal risk management module.

These dataclasses are intentionally strategy-agnostic: any trading strategy
can produce a `Signal` with an entry price, original stop loss, and fixed take
profit, and the risk module will manage the position's lifecycle from there.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PositionRiskState:
    """
    Generic state of an open position, agnostic of the strategy that opened it.

    The risk module uses this to decide when to move SL to breakeven, secure
    profits, and trail with ATR.  It is persisted in the `open_positions` table.
    """

    position_id: int
    user_id: str
    entry_price: float
    sl_original: float          # Initial SL as calculated by the strategy (swing, etc.)
    tp_fixed: Optional[float]   # Initial fixed TP (e.g. 2.0R) — replaced by far TP on Hito 2
    is_buy: bool

    # ── State machine fields ────────────────────────────────────────
    state: int = 0              # 0=start, 1=breakeven/risk-free, 2=trailing ATR
    highest_price: Optional[float] = None   # For trailing (buys)
    lowest_price: Optional[float] = None    # For trailing (sells)
    sl_current: Optional[float] = None      # Current SL sent to the broker
    spread_real: Optional[float] = None     # Spread captured once at breakeven (ask-bid)


@dataclass(frozen=True)
class RiskManagementConfig:
    """
    Risk management settings — configurable per strategy or per user.

    All R-values are relative to the original risk (|entry - sl_original|).
    """

    hito1_trigger_r: float = 1.0      # Move SL to breakeven when R >= this
    hito2_trigger_r: float = 1.5      # Secure +1.0R and activate trailing when R >= this
    hito2_sl_r: float = 1.0           # Minimum R secured in Hito 2
    breakeven_spread_mult: float = 1.0  # Spread multiplier for the breakeven SL
    trailing_enabled: bool = True
    trailing_atr_mult: float = 1.2    # Banda del trailing: max_price - mult * ATR
    trailing_atr_period: int = 14
    max_tp_far_r: float = 5.0         # Far TP used to "deactivate" the fixed TP in Hito 2
    use_candle_high_low: bool = True  # Use completed candle high/low to detect peak touches
    sl_update_retry_seconds: int = 5  # Retry delay when the broker rejects an SL update
    min_sl_update_spacing_pips: float = 1.0  # Only update SL if it improves by at least this


@dataclass(frozen=True)
class MarketSnapshot:
    """
    Market data the risk module needs for its decisions.

    The engine is responsible for populating this from whatever source it
    uses (eToro portfolio currentRate, candle high/low, computed ATR, etc.).
    """

    current_rate: float                 # currentRate from the broker (real price)
    candle_high: Optional[float] = None # High of the last COMPLETED candle (not forming)
    candle_low: Optional[float] = None  # Low of the last COMPLETED candle
    ask: Optional[float] = None         # For capturing the real spread at breakeven
    bid: Optional[float] = None
    atr: Optional[float] = None         # ATR for trailing; None → keep SL at +1.0R

    @property
    def spread(self) -> Optional[float]:
        """Current bid/ask spread, if both are present."""
        if self.ask is not None and self.bid is not None:
            return abs(self.ask - self.bid)
        return None


@dataclass(frozen=True)
class RiskDecision:
    """
    Concrete action the engine must execute against the broker.

    The engine applies the new SL/TP to eToro, and only if the broker confirms
    does it update the persisted PositionRiskState.
    """

    position_id: int
    new_stop_loss: Optional[float]
    remove_take_profit: bool          # True → move the fixed TP to max_tp_far_r
    new_state: int
    reason: str
    spread_real: Optional[float] = None  # Spread used for the breakeven (persist it)
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None