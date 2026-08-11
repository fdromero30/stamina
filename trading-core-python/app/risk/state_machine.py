"""
Pure functions for the transversal risk state machine.

These functions have NO I/O — they take a `PositionRiskState`, a
`MarketSnapshot`, and a `RiskManagementConfig`, and return either `None`
(no change needed) or a `RiskDecision` describing what the engine should
execute against the broker.
"""

from typing import Optional

from .models import (
    MarketSnapshot,
    PositionRiskState,
    RiskDecision,
    RiskManagementConfig,
)

# State constants
STATE_START = 0       # Initial: SL at -1.0R (original swing)
STATE_BREAKEVEN = 1   # Hito 1 reached: SL → breakeven + spread (risk-free)
STATE_TRAILING = 2    # Hito 2 reached: SL → +1.0R (min), trailing ATR active


# ── Helpers ────────────────────────────────────────────────────────────


def initial_risk(state: PositionRiskState) -> float:
    """Distance between entry and the ORIGINAL SL (never sl_current)."""
    return abs(state.entry_price - state.sl_original)


def compute_risk_from_price(state: PositionRiskState, price: float) -> float:
    """
    Current R multiple using the price (buy: above entry; sell: below entry).

    ALWAYS uses `sl_original` — never `sl_current` — so the R calculation
    remains consistent across state transitions.
    """
    risk = initial_risk(state)
    if risk <= 0:
        return 0.0
    if state.is_buy:
        r = (price - state.entry_price) / risk
    else:
        r = (state.entry_price - price) / risk
    # Round to 6 decimals to avoid float precision issues (e.g. 0.9999999 >= 1.0)
    return round(r, 6)


# ── Public pure functions ──────────────────────────────────────────────


def effective_price(state: PositionRiskState, snapshot: MarketSnapshot) -> float:
    """
    The "effective" price the state machine uses to detect milestone touches.

    - Primary source: currentRate from the broker (real price).
    - If `use_candle_high_low` is enabled, also considers the high/low of the
      last COMPLETED candle so intra-cycle peaks are not missed even if the
      price has already retraced by the time the bot runs.
        - Buy:  max(current_rate, candle_high)
        - Sell: min(current_rate, candle_low)
    """
    price = snapshot.current_rate
    if snapshot.candle_high is not None and state.is_buy:
        price = max(price, snapshot.candle_high)
    if snapshot.candle_low is not None and not state.is_buy:
        price = min(price, snapshot.candle_low)
    return price


def compute_breakeven_sl(
    state: PositionRiskState,
    snapshot: MarketSnapshot,
    config: RiskManagementConfig,
) -> float:
    """
    Breakeven stop-loss including the real spread.

    The spread is captured once (from snapshot.ask/bid at the moment of the
    Hito 1 transition) and persisted in `state.spread_real` — it never changes
    afterwards, so the breakeven SL never drifts between cycles.
    """
    spread = state.spread_real if state.spread_real is not None else (snapshot.spread or 0.0)
    offset = spread * config.breakeven_spread_mult
    if state.is_buy:
        return round(state.entry_price + offset, 5)
    return round(state.entry_price - offset, 5)


def compute_hito2_sl(
    state: PositionRiskState,
    config: RiskManagementConfig,
) -> float:
    """
    Secured SL for Hito 2: entry +/- hito2_sl_r * initial_risk.

    This is the minimum guaranteed profit once the position has reached
    `hito2_trigger_r` (default: secure +1.0R at 1.5R).
    """
    risk = initial_risk(state)
    if state.is_buy:
        return round(state.entry_price + config.hito2_sl_r * risk, 5)
    return round(state.entry_price - config.hito2_sl_r * risk, 5)


def compute_trailing_sl(
    state: PositionRiskState,
    snapshot: MarketSnapshot,
    config: RiskManagementConfig,
) -> float:
    """
    Trailing stop based on ATR: max_price - mult * ATR (buys).

    Rules:
    - Never retrocedes (uses the max of the new trailing level and the current
      SL level).
    - Never secures less than the Hito 2 minimum (`hito2_sl_r`).
    - If ATR is None or trailing is disabled, the Hito 2 secured SL is kept
      (safe — the position does not scale that cycle).
    """
    hito2_sl = compute_hito2_sl(state, config)

    if not config.trailing_enabled:
        return hito2_sl

    atr = snapshot.atr
    if atr is None or atr <= 0:
        return hito2_sl

    if state.is_buy:
        high = state.highest_price if state.highest_price is not None else snapshot.current_rate
        trailing = high - config.trailing_atr_mult * atr
        return round(max(trailing, hito2_sl, state.sl_current or hito2_sl), 5)

    low = state.lowest_price if state.lowest_price is not None else snapshot.current_rate
    trailing = low + config.trailing_atr_mult * atr
    current_sl = state.sl_current if state.sl_current is not None else hito2_sl
    best = min(trailing, hito2_sl)
    return round(min(best, current_sl), 5)


def _sl_improves_enough(
    old_sl: Optional[float],
    new_sl: float,
    is_buy: bool,
    min_spacing_pips: float,
    pip_size: float = 0.0001,
) -> bool:
    """
    Whether the new SL is a meaningful improvement over the current one.

    For buys, improving means new_sl > old_sl.
    For sells, improving means new_sl < old_sl.
    Requires an improvement of at least `min_spacing_pips` pips to avoid
    spamming the broker API on every cycle.
    """
    if old_sl is None:
        return True
    threshold = min_spacing_pips * pip_size
    if is_buy:
        return new_sl - old_sl >= threshold
    return old_sl - new_sl >= threshold


def evaluate(
    state: PositionRiskState,
    snapshot: MarketSnapshot,
    config: RiskManagementConfig,
) -> Optional[RiskDecision]:
    """
    Pure state-machine evaluation.

    Returns a `RiskDecision` if the position needs a broker update, or None
    if no change is required.  The decision includes the target SL, whether
    the fixed TP must be moved to the far level, and the new state.
    """
    price = effective_price(state, snapshot)
    r_now = compute_risk_from_price(state, price)

    if state.state == STATE_START:
        # Hito 1: price reached hito1_trigger_r → breakeven + spread
        if r_now >= config.hito1_trigger_r:
            new_sl = compute_breakeven_sl(state, snapshot, config)
            spread = state.spread_real if state.spread_real is not None else (snapshot.spread or 0.0)
            return RiskDecision(
                position_id=state.position_id,
                new_stop_loss=new_sl,
                remove_take_profit=False,
                new_state=STATE_BREAKEVEN,
                reason=f"Hito 1: R={r_now:.3f} >= {config.hito1_trigger_r} → breakeven SL={new_sl:.5f}",
                spread_real=spread,
                highest_price=snapshot.candle_high if state.is_buy else None,
                lowest_price=snapshot.candle_low if not state.is_buy else None,
            )
        return None

    if state.state == STATE_BREAKEVEN:
        # Hito 2: price reached hito2_trigger_r → secure hito2_sl_r and activate trailing
        if r_now >= config.hito2_trigger_r:
            high = state.highest_price
            if state.is_buy:
                high = max(high or price, price)
            low = state.lowest_price
            if not state.is_buy:
                low = min(low or price, price)

            new_sl = compute_hito2_sl(state, config)
            return RiskDecision(
                position_id=state.position_id,
                new_stop_loss=new_sl,
                remove_take_profit=True,
                new_state=STATE_TRAILING,
                reason=f"Hito 2: R={r_now:.3f} >= {config.hito2_trigger_r} → secure SL={new_sl:.5f}, TP→far",
                highest_price=high,
                lowest_price=low,
            )
        return None

    if state.state == STATE_TRAILING:
        # Trailing ATR: update highest/lowest, compute new SL, only act if it
        # improves meaningfully.
        high = state.highest_price
        low = state.lowest_price
        if state.is_buy:
            high = max(high or price, price)
        else:
            low = min(low or price, price)

        new_sl = compute_trailing_sl(state, snapshot, config)
        current_sl = state.sl_current

        improved = _sl_improves_enough(
            current_sl, new_sl, state.is_buy, config.min_sl_update_spacing_pips
        )
        if improved:
            return RiskDecision(
                position_id=state.position_id,
                new_stop_loss=new_sl,
                remove_take_profit=False,
                new_state=STATE_TRAILING,
                reason=f"Trailing: new max={high:.5f}, SL→{new_sl:.5f}",
                highest_price=high,
                lowest_price=low,
            )
        return None

    return None