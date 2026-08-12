"""
Deterministic signal generation for the trading engine.

All functions are pure: given the same inputs, they always produce the same outputs.
No randomness, no external API calls — just math.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
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
    context: Optional[dict[str, Any]] = None  # Evaluated conditions for observability
    # Order execution metadata (limit orders avoid slippage)
    order_type: str = "market"  # "market" or "limit"
    limit_price: Optional[float] = None  # required when order_type == "limit"


@dataclass(frozen=True)
class Candle:
    """A single OHLC candle."""
    open: float
    high: float
    low: float
    close: float
    timestamp: Optional[str] = None


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


def compute_atr(candles: list[Candle], period: int = 14) -> Optional[float]:
    """
    Average True Range over COMPLETED candles only.

    The last candle is treated as still forming and excluded.  Returns the
    average TR over the last ``period`` completed candles, or None if there is
    not enough data (needs at least period + 1 completed candles).
    """
    if period <= 0 or len(candles) < period + 2:
        return None

    completed = candles[:-1]  # exclude the forming candle
    if len(completed) < period + 1:
        return None

    trs: list[float] = []
    for i in range(1, len(completed)):
        tr = max(
            completed[i].high - completed[i].low,
            abs(completed[i].high - completed[i - 1].close),
            abs(completed[i].low - completed[i - 1].close),
        )
        trs.append(tr)

    if len(trs) < period:
        return None

    return sum(trs[-period:]) / period


def find_swing_low(candles: list[Candle], lookback: int) -> Optional[float]:
    """
    Find the most recent swing low in the candle data.
    A swing low is a candle whose low is lower than its neighbours.
    """
    if len(candles) < lookback + 2:
        return None

    # Only look at the most recent `lookback` completed candles
    # (exclude only the last / forming candle — not two)
    relevant = candles[-(lookback + 1):-1]
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

    relevant = candles[-(lookback + 1):-1]
    if not relevant:
        return None

    # Search from right to left (most recent first) to find the most recent swing high
    for i in range(len(relevant) - 2, 0, -1):
        if relevant[i].high > relevant[i - 1].high and relevant[i].high > relevant[i + 1].high:
            return relevant[i].high

    return max(c.high for c in relevant)


def find_ma_crossover_index(
    prices: list[float],
    short_ma: list[float],
    window: int = 3,
    exclude_forming: bool = True,
) -> Optional[int]:
    """
    Find the index of the most recent candle where price crossed the short MA.

    The crossover is only confirmed on COMPLETED candles: the last candle is
    treated as still forming and excluded by default.  A small window (default
    3) is scanned backwards so a crossover that happened 1-2 candles ago is not
    missed when the scheduler runs slightly late (this was the root cause of
    signals that appeared on the chart but were never turned into orders).

    Returns the index ``i`` of the candle where the price crossed (``prices[i]``
    is the "now" side of the pair), or None if no crossover is found.
    """
    if len(prices) < 3 or len(short_ma) < 3:
        return None

    # Align short_ma with prices.  compute_sma() returns
    # len(prices) - period + 1 values, so the LAST SMA value corresponds to the
    # LAST price.  We pad the front so that short_ma[i] aligns with prices[i].
    if len(short_ma) < len(prices):
        pad = len(prices) - len(short_ma)
        short_ma = [short_ma[0]] * pad + list(short_ma)

    # Index of the last candle we are allowed to use as the "current" side of
    # the crossover pair.  If the last candle is still forming, exclude it.
    end = len(prices) - (1 if exclude_forming else 0)
    if end < 2:
        return None

    prev_end = end - 1  # last index of a completed crossover pair
    start = max(1, prev_end - window + 1)

    # Scan backwards so the MOST RECENT crossover wins.
    for i in range(prev_end, start - 1, -1):
        # Bullish crossover: price was at/below the short MA, now above
        if prices[i - 1] <= short_ma[i - 1] and prices[i] > short_ma[i]:
            return i

        # Bearish crossover: price was at/above the short MA, now below
        if prices[i - 1] >= short_ma[i - 1] and prices[i] < short_ma[i]:
            return i

    return None


def detect_ma_crossover(
    prices: list[float],
    short_ma: list[float],
    long_ma: list[float],
    window: int = 3,
    exclude_forming: bool = True,
) -> Optional[str]:
    """
    Detect the most recent price/short-MA crossover within a window of
    recently COMPLETED candles.

    The last candle is treated as still forming and excluded by default, so a
    crossover is only confirmed on closed candles.  A small window (default 3)
    is scanned backwards so a crossover that happened 1-2 candles ago is not
    missed when the scheduler runs slightly late (this was the root cause of
    signals that appeared on the chart but were never turned into orders).

    Returns 'bullish' (price crossed above the short MA), 'bearish' (price
    crossed below the short MA), or None.
    """
    # Align short_ma with prices the same way find_ma_crossover_index does.
    if len(short_ma) < len(prices):
        pad = len(prices) - len(short_ma)
        short_ma = [short_ma[0]] * pad + list(short_ma)

    idx = find_ma_crossover_index(
        prices, short_ma, window=window, exclude_forming=exclude_forming
    )
    if idx is None:
        return None

    # Bullish crossover: price was at/below the short MA, now above
    if prices[idx - 1] <= short_ma[idx - 1] and prices[idx] > short_ma[idx]:
        return "bullish"

    # Bearish crossover: price was at/above the short MA, now below
    if prices[idx - 1] >= short_ma[idx - 1] and prices[idx] < short_ma[idx]:
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


# ── Feed Diagnostics (instrumentación) ───────────────────────────────────


def _build_feed_diagnostics(
    candles: list[Candle],
    closes: list[float],
    ma_short_aligned: list[float],
) -> dict[str, Any]:
    """Snapshot de diagnóstico del feed de velas (NO invasivo)."""
    now_utc = datetime.now(timezone.utc)
    diag: dict[str, Any] = {"now_utc": now_utc.isoformat(), "interval_hint_seconds": 300}

    if len(candles) < 2:
        return diag

    last = candles[-1]
    prev = candles[-2]

    last_age_seconds: Optional[int] = None
    ts = last.timestamp
    if ts is not None:
        try:
            if isinstance(ts, str) and ts.isdigit():
                ts_sec = float(ts) / 1000 if len(ts) >= 13 else float(ts)
                last_open = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
            else:
                iso = str(ts).replace("Z", "+00:00")
                if "+" in iso:
                    base, _, tz_part = iso.partition("+")
                    if "." in base:
                        int_part, _, frac = base.partition(".")
                        base = f"{int_part}.{frac[:3]}"
                    iso = f"{base}+{tz_part}"
                last_open = datetime.fromisoformat(iso)
            last_age_seconds = max(0, int((now_utc - last_open).total_seconds()))
        except Exception:
            last_age_seconds = None

    diag.update({
        "last_candle_time": last.timestamp,
        "last_candle_age_seconds": last_age_seconds,
        "last_close": round(last.close, 5),
        "last_ma9": round(ma_short_aligned[-1], 5) if len(ma_short_aligned) > 0 else None,
        "penultimate_candle_time": prev.timestamp,
        "penultimate_close": round(prev.close, 5),
        "penultimate_ma9": round(ma_short_aligned[-2], 5) if len(ma_short_aligned) > 1 else None,
    })

    if len(closes) >= 2 and len(ma_short_aligned) >= 2:
        diag["last_crosses_up"] = closes[-1] > ma_short_aligned[-1] and closes[-2] <= ma_short_aligned[-2]
        diag["last_crosses_down"] = closes[-1] < ma_short_aligned[-1] and closes[-2] >= ma_short_aligned[-2]

    if len(closes) >= 3 and len(ma_short_aligned) >= 3:
        diag["evaluated_crosses_up"] = closes[-2] > ma_short_aligned[-2] and closes[-3] <= ma_short_aligned[-3]
        diag["evaluated_crosses_down"] = closes[-2] < ma_short_aligned[-2] and closes[-3] >= ma_short_aligned[-3]

    return diag


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
    crossover_window: int = 1,
    risk_reward_ratio: float = 2.0,
    atr_period: int = 14,
    max_candle_expansion_atr_mult: float = 1.8,
) -> Signal:
    """
    Evaluate the MA200 + MA9 strategy.

    Rules:
    - Price > MA200 → only BUY signals when the MA9 cross is CONFIRMED on the
      most recent completed candle (crossover_window=1 by default: we wait for
      the candle to CLOSE and enter at its close via a LIMIT order).
    - Price < MA200 → only SELL signals when the MA9 cross is confirmed on the
      most recent completed candle.
    - Max `max_positions` open positions at a time.
    - SL = swing low (for buy) / swing high (for sell) before crossover.
    - TP = risk_reward_ratio : 1.
    - Expansion filter: the entry is DISCARDED when the confirmation candle's
      body is larger than max_candle_expansion_atr_mult × ATR(atr_period)
      (avoids entering far from the optimal level after a news/expansion candle).
    """
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

    # Align both MAs to the full price array so that ma_*[i] corresponds to
    # closes[i].  compute_sma() returns len(prices) - period + 1 values, so the
    # missing front values are padded with the first SMA value.
    def _align_ma(ma: list[float]) -> list[float]:
        if len(ma) < len(closes):
            pad = len(closes) - len(ma)
            return [ma[0]] * pad + list(ma)
        return ma

    ma_short_aligned = _align_ma(ma_short)
    ma_long_aligned = _align_ma(ma_long)

    # ── Detect crossover (on COMPLETED candles only) ────────────────
    crossover_index = find_ma_crossover_index(
        closes, ma_short, window=crossover_window
    )
    crossover = detect_ma_crossover(
        closes, ma_short, ma_long, window=crossover_window
    )

    # Use the price/MA of the candle where the crossover happened, NOT the
    # still-forming last candle.  This is the real entry reference for the
    # limit order and the correct trend filter (price vs MA200).
    if crossover_index is not None:
        trend_price = closes[crossover_index]
        trend_ma200 = ma_long_aligned[crossover_index]
        crossover_close = closes[crossover_index]
    else:
        # No crossover; fall back to the last completed candle (close of
        # candles[-2]) so the context values stay meaningful.
        trend_price = closes[-2] if len(closes) > 1 else closes[-1]
        trend_ma200 = ma_long[-2] if len(ma_long) > 1 else ma_long[-1]
        crossover_close = trend_price

    price_above_ma200 = trend_price > trend_ma200
    price_below_ma200 = trend_price < trend_ma200

    # Build the context of evaluated conditions for observability
    context: dict[str, Any] = {
        "candles_count": len(candles),
        "ma_short_period": strategy.ma_short_period,
        "ma_long_period": strategy.ma_long_period,
        "ma_short_value": round(ma_short[-1], 5) if ma_short else None,
        "ma_long_value": round(ma_long[-1], 5),
        "current_price": round(closes[-1], 5),
        "trend_price": round(trend_price, 5),
        "trend_ma200": round(trend_ma200, 5),
        "crossover_index": crossover_index,
        "crossover_close": round(crossover_close, 5),
        "bid": market_data.bid,
        "ask": market_data.ask,
        "price_above_ma200": price_above_ma200,
        "price_below_ma200": price_below_ma200,
        "crossover": crossover,
        "open_positions_count": open_positions_count,
        "max_positions": max_positions,
        "account_balance": account_balance,
        "risk_per_trade": risk_per_trade,
        "swing_lookback": swing_lookback,
        "crossover_window": crossover_window,
        "risk_reward_ratio": risk_reward_ratio,
        # Diagnóstico del feed (no invasivo) para depurar cruces perdidos
        "feed_diagnostics": _build_feed_diagnostics(candles, closes, ma_short_aligned),
    }

    if len(candles) < strategy.ma_long_period + 10:
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason=f"Not enough candles: {len(candles)} < {strategy.ma_long_period + 10}",
            context=context,
        )

    if crossover is None:
        # Incluir diagnóstico del feed en el reason para visibilidad inmediata
        diag: dict[str, Any] = context.get("feed_diagnostics") or {}
        reason_parts = ["No MA crossover detected"]
        if diag.get("last_crosses_up") or diag.get("last_crosses_down"):
            reason_parts.append(
                f"cruce-en-EXCLUIDA(up={diag.get('last_crosses_up')},down={diag.get('last_crosses_down')})"
            )
        if diag.get("evaluated_crosses_up") or diag.get("evaluated_crosses_down"):
            reason_parts.append(
                f"cruce-en-evaluada(up={diag.get('evaluated_crosses_up')},down={diag.get('evaluated_crosses_down')})"
            )
        if diag.get("last_candle_age_seconds") is not None:
            age = diag["last_candle_age_seconds"]
            reason_parts.append(f"last_candle_age={age}s{'>300' if age > 300 else ''}")
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason=" | ".join(reason_parts),
            context=context,
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
            context=context,
        )

    # ── Expansion Filter (ATR) ─────────────────────────────────────
    # If the confirmation candle (the one that closed the cross) is an
    # abnormally large expansion candle, the entry is DISCARDED: entering at
    # the next candle's open/close would be far from the optimal level.
    assert crossover_index is not None
    confirmation_candle = candles[crossover_index]
    candle_body = abs(confirmation_candle.close - confirmation_candle.open)

    atr = compute_atr(candles, atr_period)
    if atr is not None and candle_body > max_candle_expansion_atr_mult * atr:
        context.update({
            "candle_body": round(candle_body, 5),
            "atr": round(atr, 5),
            "atr_threshold": round(max_candle_expansion_atr_mult * atr, 5),
            "expansion_filtered": True,
        })
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason=(
                f"Entrada descartada por filtro de expansión: body={candle_body:.5f} "
                f"> {max_candle_expansion_atr_mult:.1f}×ATR({atr_period})="
                f"{max_candle_expansion_atr_mult*atr:.5f}"
            ),
            context=context,
        )

    context["expansion_filtered"] = False

    # ── Evaluate signal based on trend ──────────────────────────────
    # Use the CLOSE of the completed crossover candle as the limit price.
    # This avoids slippage: we place a LIMIT order at the exact price that
    # triggered the signal instead of chasing the market at the current bid/ask.
    limit_price = round(crossover_close, 5)
    entry_price = limit_price

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
                context=context,
            )

        take_profit = calculate_take_profit(
            entry_price, stop_loss, risk_reward_ratio, is_buy=True
        )
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
                context=context,
            )

        context.update({
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "units": units,
        })

        return Signal(
            action=SignalAction.BUY,
            confidence=0.8,
            units=units,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=f"BUY: price {trend_price:.5f} > MA200 {trend_ma200:.5f}, "
                   f"crossed above MA9. Limit={limit_price:.5f}, SL={stop_loss:.5f}, TP={take_profit:.5f}",
            context=context,
            order_type="limit",
            limit_price=limit_price,
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
                context=context,
            )

        take_profit = calculate_take_profit(
            entry_price, stop_loss, risk_reward_ratio, is_buy=False
        )
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
                context=context,
            )

        context.update({
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "units": units,
        })

        return Signal(
            action=SignalAction.SELL,
            confidence=0.8,
            units=units,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=f"SELL: price {trend_price:.5f} < MA200 {trend_ma200:.5f}, "
                   f"crossed below MA9. Limit={limit_price:.5f}, SL={stop_loss:.5f}, TP={take_profit:.5f}",
            context=context,
            order_type="limit",
            limit_price=limit_price,
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
        context=context,
    )
