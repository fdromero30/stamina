"""
Deterministic signal generation for the trading engine.

All functions are pure: given the same inputs, they always produce the same outputs.
No randomness, no external API calls — just math.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Optional


class SignalAction(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True)
class Signal:
    """Output of the signal evaluation — deterministic."""
    action: SignalAction
    confidence: float  # 0.0 to 1.0
    units: float
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str


@dataclass(frozen=True)
class Candle:
    """A single OHLC candle."""
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class MarketData:
    """Current market snapshot from the rates endpoint."""
    bid: float
    ask: float
    instrument_id: int


@dataclass(frozen=True)
class StrategyConfig:
    """Strategy parameters as received from the Java backend."""
    id: str
    user_id: str
    symbol: str
    enabled: bool
    ma_short_period: int
    ma_long_period: int
    max_position_size: Optional[float]
    max_open_positions: Optional[int]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    break_even_trigger: Optional[float]
    # Additional fields for future strategies
    use_ml: bool
    ml_strategy_code: Optional[str]


# ── Technical Indicators ────────────────────────────────────────────────


def compute_sma(prices: list[float], period: int) -> list[float]:
    """Simple Moving Average — pure function."""
    if len(prices) < period or period <= 0:
        return []
    sma: list[float] = []
    for i in range(len(prices) - period + 1):
        sma.append(sum(prices[i:i + period]) / period)
    return sma


def find_swing_low(candles: list[Candle], lookback: int) -> Optional[float]:
    """
    Find the most recent swing low in the candle data.
    A swing low is a candle whose low is lower than its neighbours.
    """
    if len(candles) < lookback + 2:
        return None

    # Only look at the most recent `lookback` candles
    relevant = candles[-(lookback + 2):-2]  # exclude the last 2 candles (current forming)
    if not relevant:
        return None

    # Search from right to left (most recent first) to find the most recent swing low
    for i in range(len(relevant) - 2, 0, -1):
        if relevant[i].low < relevant[i - 1].low and relevant[i].low < relevant[i + 1].low:
            return relevant[i].low

    # Fallback: just use the minimum low in the window
    return min(c.low for c in relevant)


def find_swing_high(candles: list[Candle], lookback: int) -> Optional[float]:
    """
    Find the most recent swing high in the candle data.
    A swing high is a candle whose high is higher than its neighbours.
    """
    if len(candles) < lookback + 2:
        return None

    relevant = candles[-(lookback + 2):-2]
    if not relevant:
        return None

    # Search from right to left (most recent first) to find the most recent swing high
    for i in range(len(relevant) - 2, 0, -1):
        if relevant[i].high > relevant[i - 1].high and relevant[i].high > relevant[i + 1].high:
            return relevant[i].high

    return max(c.high for c in relevant)


def detect_ma_crossover(
    prices: list[float],
    short_ma: list[float],
    long_ma: list[float],
) -> Optional[str]:
    """
    Detect if the last completed candle caused a crossover.
    Returns 'bullish' if price crossed above MA, 'bearish' if below, None otherwise.
    """
    if len(prices) < 3 or len(short_ma) < 3 or len(long_ma) < 3:
        return None

    # Align: the last element of short_ma/long_ma corresponds to the last price
    # We need to check the current vs previous candle
    price_now = prices[-1]
    price_prev = prices[-2]

    short_now = short_ma[-1]
    short_prev = short_ma[-2]

    # Bullish crossover: price was below MA9, now above
    if price_prev <= short_prev and price_now > short_now:
        return "bullish"

    # Bearish crossover: price was above MA9, now below
    if price_prev >= short_prev and price_now < short_now:
        return "bearish"

    return None


# ── Position Sizing ──────────────────────────────────────────────────────


def calculate_units(
    account_balance: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss: float,
) -> float:
    """
    Calculate position size based on fixed-fractional risk management.
    risk = account_balance * risk_per_trade
    units = risk / |entry - stop_loss|
    """
    if stop_loss <= 0 or entry_price <= 0:
        return 0.0

    risk_amount = account_balance * risk_per_trade
    price_risk = abs(entry_price - stop_loss)
    if price_risk <= 0:
        return 0.0

    units = risk_amount / price_risk
    return round(units, 2)


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    risk_reward_ratio: float = 2.0,
    is_buy: bool = True,
) -> float:
    """Calculate TP price based on risk:reward ratio."""
    risk = abs(entry_price - stop_loss)
    if is_buy:
        return round(entry_price + risk * risk_reward_ratio, 5)
    else:
        return round(entry_price - risk * risk_reward_ratio, 5)


def calculate_breakeven_stop_loss(
    entry_price: float,
    spread: float = 0.0001,
    is_buy: bool = True,
) -> float:
    """
    Calculate the breakeven stop loss price, accounting for spread/fees.
    For buy: breakeven = entry + spread (need price to cover spread)
    For sell: breakeven = entry - spread
    """
    if is_buy:
        return round(entry_price + spread, 5)
    else:
        return round(entry_price - spread, 5)


# ── Main Evaluator ───────────────────────────────────────────────────────


def evaluate_ma_strategy(
    strategy: StrategyConfig,
    candles: list[Candle],
    market_data: MarketData,
    account_balance: float,
    open_positions_count: int,
    swing_lookback: int = 20,
    risk_per_trade: float = 0.005,
    max_positions: int = 2,
) -> Signal:
    """
    Evaluate the MA200 + MA9 strategy.

    Rules:
    - Price > MA200 → only BUY signals when price crosses above MA9
    - Price < MA200 → only SELL signals when price crosses below MA9
    - Max `max_positions` open positions at a time
    - SL = swing low (for buy) / swing high (for sell) before crossover
    - TP = 2:1 risk:reward
    """
    if len(candles) < strategy.ma_long_period + 10:
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason=f"Not enough candles: {len(candles)} < {strategy.ma_long_period + 10}",
        )

    # ── Calculate MAs ──────────────────────────────────────────────
    closes = [c.close for c in candles]
    ma_short = compute_sma(closes, strategy.ma_short_period)
    ma_long = compute_sma(closes, strategy.ma_long_period)

    if not ma_short or not ma_long:
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason="Failed to compute MAs",
        )

    # ── Check trend direction (price vs MA200) ──────────────────────
    current_price = closes[-1]
    current_ma200 = ma_long[-1]

    price_above_ma200 = current_price > current_ma200
    price_below_ma200 = current_price < current_ma200

    # ── Detect crossover ────────────────────────────────────────────
    crossover = detect_ma_crossover(closes, ma_short, ma_long)

    if crossover is None:
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason="No MA crossover detected",
        )

    # ── Check position limits ───────────────────────────────────────
    if open_positions_count >= max_positions:
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason=f"Max positions reached ({open_positions_count}/{max_positions})",
        )

    # ── Evaluate signal based on trend ──────────────────────────────
    entry_price = market_data.ask if crossover == "bullish" else market_data.bid

    if crossover == "bullish" and price_above_ma200:
        # BUY signal: price above MA200 and crossed above MA9
        stop_loss = find_swing_low(candles, swing_lookback)
        if stop_loss is None or stop_loss >= entry_price:
            return Signal(
                action=SignalAction.HOLD,
                confidence=0.0,
                units=0.0,
                entry_price=0.0,
                stop_loss=None,
                take_profit=None,
                reason="No valid swing low found for SL placement",
            )

        take_profit = calculate_take_profit(entry_price, stop_loss, 2.0, is_buy=True)
        units = calculate_units(account_balance, risk_per_trade, entry_price, stop_loss)

        if units <= 0:
            return Signal(
                action=SignalAction.HOLD,
                confidence=0.0,
                units=0.0,
                entry_price=0.0,
                stop_loss=None,
                take_profit=None,
                reason=f"Calculated units too low: {units}",
            )

        return Signal(
            action=SignalAction.BUY,
            confidence=0.8,
            units=units,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=f"BUY: price {current_price:.5f} > MA200 {current_ma200:.5f}, "
                   f"crossed above MA9. SL={stop_loss:.5f}, TP={take_profit:.5f}",
        )

    elif crossover == "bearish" and price_below_ma200:
        # SELL signal: price below MA200 and crossed below MA9
        stop_loss = find_swing_high(candles, swing_lookback)
        if stop_loss is None or stop_loss <= entry_price:
            return Signal(
                action=SignalAction.HOLD,
                confidence=0.0,
                units=0.0,
                entry_price=0.0,
                stop_loss=None,
                take_profit=None,
                reason="No valid swing high found for SL placement",
            )

        take_profit = calculate_take_profit(entry_price, stop_loss, 2.0, is_buy=False)
        units = calculate_units(account_balance, risk_per_trade, entry_price, stop_loss)

        if units <= 0:
            return Signal(
                action=SignalAction.HOLD,
                confidence=0.0,
                units=0.0,
                entry_price=0.0,
                stop_loss=None,
                take_profit=None,
                reason=f"Calculated units too low: {units}",
            )

        return Signal(
            action=SignalAction.SELL,
            confidence=0.8,
            units=units,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=f"SELL: price {current_price:.5f} < MA200 {current_ma200:.5f}, "
                   f"crossed below MA9. SL={stop_loss:.5f}, TP={take_profit:.5f}",
        )

    # Signal direction doesn't match trend
    return Signal(
        action=SignalAction.HOLD,
        confidence=0.0,
        units=0.0,
        entry_price=0.0,
        stop_loss=None,
        take_profit=None,
        reason=f"Crossover direction ({crossover}) doesn't match trend "
               f"(above_MA200={price_above_ma200})",
    )