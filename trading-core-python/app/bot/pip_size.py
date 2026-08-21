"""Dynamic pip-size calculation from real market prices.

Instead of hardcoding a pip size per symbol, this module derives it from the
decimal precision of the actual prices eToro returns (rates + candles).

Examples (verified against the real eToro API):
- EUR/USD: prices like 1.15743 → 5 decimals → pip = 0.0001
- USD/JPY: prices like 151.342  → 3 decimals → pip = 0.01
- GOLD:    prices like 4406.17  → 2 decimals → pip = 0.01
"""

import logging
import math
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# Fallback pip size when prices cannot be inspected (FX convention).
DEFAULT_PIP_SIZE = 0.0001

# Minimum number of distinct prices required before trusting the inference.
_MIN_SAMPLE_POINTS = 3


def _decimal_places(value: float) -> int:
    """Count significant decimal places in a float price."""
    if value is None or not math.isfinite(value) or value <= 0:
        return 0
    # Convert to string to inspect the exact representation eToro sent us.
    # eToro prices arrive as JSON numbers (e.g. 1.15743, 4406.17, 4402.9).
    # Using the shortest round-trip repr mirrors what the JSON parser saw.
    text = repr(value)
    if "." not in text:
        return 0
    places = len(text.split(".")[1])
    # Trailing zeros are dropped by the JSON parser (4402.90 → 4402.9), so
    # the true precision can be one more than what a single value shows.
    # We pick the MAX places seen across the sample to recover that.
    return places


def calculate_pip_size(prices: Iterable[Optional[float]]) -> float:
    """
    Calculate the pip size from a sample of real prices.

    Uses the maximum number of decimal places observed across the sample:
        places = 5  → pip = 10^-4 = 0.0001   (EUR/USD)
        places = 4  → pip = 10^-3 = 0.001
        places = 3  → pip = 10^-2 = 0.01     (USD/JPY)
        places = 2  → pip = 10^-2 = 0.01     (GOLD)
        places = 1  → pip = 10^-1 = 0.1
        places = 0  → pip = 1.0

    The convention maps (places - 1) to the pip exponent for price quoting:
        pip = 10 ** -(places - 1)

    Falls back to ``DEFAULT_PIP_SIZE`` when the sample is too small or no
    valid price is present.
    """
    places_seen: list[int] = []
    for p in prices:
        if p is None or not math.isfinite(p) or p <= 0:
            continue
        places_seen.append(_decimal_places(float(p)))

    if len(places_seen) < _MIN_SAMPLE_POINTS:
        logger.debug(
            "Not enough price samples to infer pip size (%d < %d) — using default %.4f",
            len(places_seen), _MIN_SAMPLE_POINTS, DEFAULT_PIP_SIZE,
        )
        return DEFAULT_PIP_SIZE

    max_places = max(places_seen)

    # GOLD/BTC/ETH on eToro are quoted with 1-2 decimals: max can be 2, but a
    # single 3-decimal print (e.g. 4402.900 if the feed prints a trailing tail)
    # would incorrectly push pip to 0.001.  Clamp to a sane ceiling: the
    # minimum pip size we ever use is 0.0001 (FX 5-decimal feeds).
    pip = 10 ** -(max_places - 1)
    pip = max(pip, DEFAULT_PIP_SIZE)

    logger.debug(
        "Inferred pip size %.5f from %d price samples (max decimals=%d)",
        pip, len(places_seen), max_places,
    )
    return pip


def infer_pip_size_from_candles(candles) -> float:
    """Infer the pip size from a list of Candle objects (app.bot.signals.Candle)."""
    prices: list[Optional[float]] = []
    for c in candles:
        prices.extend([c.open, c.high, c.low, c.close])
    return calculate_pip_size(prices)