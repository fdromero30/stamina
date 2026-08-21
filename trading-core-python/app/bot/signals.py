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


def candle_age_seconds(candle: Candle) -> Optional[int]:
    """
    Seconds elapsed since the candle's OPENING timestamp (UTC now).

    Returns None if the timestamp cannot be parsed.
    A closed M5 candle has age >= 300.  A forming candle has age < 300.
    """
    if candle.timestamp is None:
        return None
    ts = candle.timestamp
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
        return max(0, int((datetime.now(timezone.utc) - last_open).total_seconds()))
    except Exception:
        return None


def is_candle_complete(candles: list[Candle], interval_seconds: int = 300) -> bool:
    """
    Determine whether the LAST candle in the feed is already CLOSED.

    Uses the candle's OPENING timestamp: if `interval_seconds` have elapsed
    since the candle opened, it is considered closed (a new candle should have
    started by now, but the feed may not have delivered it yet).

    If the timestamp is unavailable, fall back to the old assumption that the
    last candle is still forming (conservative: always exclude it).
    """
    if not candles:
        return False
    age = candle_age_seconds(candles[-1])
    if age is None:
        return False  # cannot verify → assume forming
    return age >= interval_seconds


def find_ma_crossover_index(
    prices: list[float],
    short_ma: list[float],
    window: int = 3,
    exclude_forming: bool = True,
    last_candle_closed: bool = False,
) -> Optional[int]:
    """
    Find the index of the most recent candle where price crossed the short MA.

    The crossover is only confirmed on COMPLETED candles: the last candle is
    treated as still forming and excluded by default.  A small window (default
    3) is scanned backwards so a crossover that happened 1-2 candles ago is not
    missed when the scheduler runs slightly late (this was the root cause of
    signals that appeared on the chart but were never turned into orders).

    ``last_candle_closed``: set True when the strategy verified (via timestamp)
    that the final candle in the feed is already CLOSED (aging >= interval).
    In that case the final candle is NOT excluded, so a crossover on the
    most-recently-closed candle is not lost to feed latency.

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

    # If the caller verified the last candle is already closed, treat it as a
    # completed candle (the feed may not have delivered the forming one yet).
    actual_exclude = exclude_forming and not last_candle_closed

    # Index of the last candle we are allowed to use as the "current" side of
    # the crossover pair.  If the last candle is still forming, exclude it.
    end = len(prices) - (1 if actual_exclude else 0)
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
    last_candle_closed: bool = False,
) -> Optional[str]:
    """
    Detect the most recent price/short-MA crossover within a window of
    recently COMPLETED candles.

    The last candle is treated as still forming and excluded by default, so a
    crossover is only confirmed on closed candles.  A small window (default 3)
    is scanned backwards so a crossover that happened 1-2 candles ago is not
    missed when the scheduler runs slightly late (this was the root cause of
    signals that appeared on the chart but were never turned into orders).

    ``last_candle_closed``: set True when the strategy verified (via timestamp)
    that the final candle in the feed is already CLOSED — it is then treated as
    a completed candle so the most-recently-closed crossover is not lost.

    Returns 'bullish' (price crossed above the short MA), 'bearish' (price
    crossed below the short MA), or None.
    """
    # Align short_ma with prices the same way find_ma_crossover_index does.
    if len(short_ma) < len(prices):
        pad = len(prices) - len(short_ma)
        short_ma = [short_ma[0]] * pad + list(short_ma)

    idx = find_ma_crossover_index(
        prices, short_ma, window=window, exclude_forming=exclude_forming,
        last_candle_closed=last_candle_closed,
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
    sl_atr_multiplier: float = 1.5,
    sl_min_distance_pips: float = 10.0,
    pip_size: float = 0.0001,
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
    - ``pip_size``: size of one pip in price (0.0001 for EUR/USD, 0.01 for
      GOLD).  Used to convert pip-based thresholds to price.
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
    # Determina si la última vela del feed YA está cerrada (por timestamp).
    # Si el feed tarda en publicar la vela siguiente, candles[-1] es en
    # realidad la vela recién cerrada — no debe descartarse por "formándose".
    last_candle_closed = is_candle_complete(candles)

    crossover_index = find_ma_crossover_index(
        closes, ma_short, window=crossover_window,
        last_candle_closed=last_candle_closed,
    )
    crossover = detect_ma_crossover(
        closes, ma_short, ma_long, window=crossover_window,
        last_candle_closed=last_candle_closed,
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
        "last_candle_closed": last_candle_closed,
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

    # ── SL: ATR-based (regla: SL = MA200 ∓ sl_atr_multiplier × ATR14) ──
    # El ATR ya se calculó arriba para el filtro de expansión.  Para dar
    # "aire" al SL y que eToro no lo rechace:
    #   BUY  → SL = MA200 − (mult × ATR14)
    #   SELL → SL = MA200 + (mult × ATR14)
    is_buy = crossover == "bullish"

    if atr is None:
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason="ATR unavailable, cannot place SL",
            context=context,
        )

    # pips → precio (1 pip = pip_size; 0.0001 para FX, 0.01 para GOLD/xmetals)
    min_sl_distance_price = sl_min_distance_pips * pip_size

    if is_buy:
        stop_loss = trend_ma200 - sl_atr_multiplier * atr
    else:
        stop_loss = trend_ma200 + sl_atr_multiplier * atr

    sl_distance = abs(stop_loss - entry_price)

    # Piso de seguridad: si MA200 ∓ ATR deja el SL demasiado cerca del entry,
    # expandirlo a la distancia mínima para que eToro no rechace la orden.
    if sl_distance < min_sl_distance_price:
        if is_buy:
            stop_loss = entry_price - min_sl_distance_price
        else:
            stop_loss = entry_price + min_sl_distance_price
        sl_distance = abs(stop_loss - entry_price)

    # Validar dirección: BUY → SL < entry; SELL → SL > entry
    if (is_buy and stop_loss >= entry_price) or (not is_buy and stop_loss <= entry_price):
        context.update({
            "sl_basis": "ma200_atr",
            "atr_value": round(atr, 5),
            "atr_multiplier": round(sl_atr_multiplier, 3),
            "sl_value": round(stop_loss, 5),
            "min_sl_distance_pips": sl_min_distance_pips,
            "sl_reason": "SL direction invalid relative to entry",
        })
        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            units=0.0,
            entry_price=0.0,
            stop_loss=None,
            take_profit=None,
            reason=(
                f"Invalid SL direction for {'BUY' if is_buy else 'SELL'}: "
                f"SL={stop_loss:.5f}, entry={entry_price:.5f}"
            ),
            context=context,
        )

    take_profit = calculate_take_profit(
        entry_price, stop_loss, risk_reward_ratio, is_buy=is_buy
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
        "sl_basis": "ma200_atr",
        "atr_value": round(atr, 5),
        "atr_multiplier": round(sl_atr_multiplier, 3),
        "sl_distance_pips": round(sl_distance / pip_size, 2),
        "min_sl_distance_pips": sl_min_distance_pips,
        "pip_size": pip_size,
    })

    action = SignalAction.BUY if is_buy else SignalAction.SELL
    direction_word = "above" if is_buy else "below"
    comp_word = ">" if is_buy else "<"
    reason = (
        f"{action.name}: price {trend_price:.5f} {comp_word} MA200 {trend_ma200:.5f}, "
        f"crossed {direction_word} MA9. Limit={limit_price:.5f}, "
        f"SL={stop_loss:.5f} (MA200 {'∓' if is_buy else '∓'} {sl_atr_multiplier}×ATR), "
        f"TP={take_profit:.5f}"
    )

    return Signal(
        action=action,
        confidence=0.8,
        units=units,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
        context=context,
        order_type="limit",
        limit_price=limit_price,
    )
