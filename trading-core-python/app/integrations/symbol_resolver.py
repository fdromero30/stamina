"""Resolve user-facing symbols (BTCUSD, EUR/USD, BTCUSDT, ...) to eToro instrument IDs.

The eToro ``/market-data/instruments`` endpoint returns the FULL universe of
instruments (16k+) regardless of ``searchText``, so we must match the requested
symbol ourselves.  This resolver uses three layers, in order:

1. Static alias map    — fast, no network (BTC/USD -> BTC, XAUUSD -> XAUUSD, ...)
2. Heuristic normalize — strip exchange suffixes (USDT, USDC, PERP) and slashes
3. Cached catalogue    — download the full instrument list once (TTL 1h) and
                         match exact symbolFull/displayname, then substring
"""

import logging
import time
from typing import Any, Optional

from app.integrations.orders_client import EtoroHttpClient

logger = logging.getLogger(__name__)

# ── Layer 1: Static aliases ─────────────────────────────────────────────
# Map common user-facing symbols to the canonical eToro symbolFull.
SYMBOL_ALIASES: dict[str, str] = {
    # Crypto
    "BTC": "BTC",
    "BTCUSD": "BTC",
    "BTC/USD": "BTC",
    "BTCUSDT": "BTC",
    "XBT": "BTC",
    "BITCOIN": "BTC",
    "ETH": "ETH",
    "ETHUSD": "ETH",
    "ETH/USD": "ETH",
    "ETHUSDT": "ETH",
    "ETHER": "ETH",
    "XRP": "XRP",
    "XRPUSD": "XRP",
    "SOL": "SOL",
    "SOLUSD": "SOL",
    "SOLUSDT": "SOL",
    "ADA": "ADA",
    "DOGE": "DOGE",
    "LTC": "LTC",
    # Forex
    "EURUSD": "EURUSD",
    "EUR/USD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "GBP/USD": "GBPUSD",
    "USDJPY": "USDJPY",
    "USD/JPY": "USDJPY",
    "AUDUSD": "AUDUSD",
    "AUD/USD": "AUDUSD",
    "USDCAD": "USDCAD",
    "USD/CAD": "USDCAD",
    "USDCHF": "USDCHF",
    "USD/CHF": "USDCHF",
    "NZDUSD": "NZDUSD",
    "NZD/USD": "NZDUSD",
    "EURGBP": "EURGBP",
    "EUR/GBP": "EURGBP",
    "EURJPY": "EURJPY",
    "EUR/JPY": "EURJPY",
    # Metals
    "XAUUSD": "XAUUSD",
    "XAU/USD": "XAUUSD",
    "GOLD": "XAUUSD",
    "XAGUSD": "XAGUSD",
    "XAG/USD": "XAGUSD",
    "SILVER": "XAGUSD",
    # Indices
    "SPX500": "SPX500",
    "NAS100": "NAS100",
    "US100": "NAS100",
    "US30": "US30",
    "DJ30": "US30",
    "GER40": "GER40",
    "DAX": "GER40",
    # Popular US stocks
    "AAPL": "AAPL",
    "TSLA": "TSLA",
    "NVDA": "NVDA",
    "AMZN": "AMZN",
    "MSFT": "MSFT",
    "META": "META",
    "GOOGL": "GOOGL",
    "NFLX": "NFLX",
}

# ── Layer 2: Heuristic normalization ─────────────────────────────────────
_EXCHANGE_SUFFIXES = ("USDT", "USDC", "BUSD", "PERP", "SPOT", "FDUSD", "DOWN", "UP")


def _normalize_symbol(symbol: str) -> str:
    """Normalize a user symbol: uppercase, remove slashes/spaces/hyphens."""
    s = symbol.upper().replace("/", "").replace("-", "").replace(" ", "").strip()
    return s


def _strip_exchange_suffix(symbol: str) -> str:
    """Remove common exchange suffixes to recover the base asset."""
    s = symbol.upper()
    for suffix in _EXCHANGE_SUFFIXES:
        if s.endswith(suffix) and len(s) > len(suffix):
            return s[: -len(suffix)]
    return s


# ── Layer 3 cache record ────────────────────────────────────────────────


class SymbolResolver:
    """Shared resolver that maps user symbols to eToro instrument IDs.

    Usage::

        resolver = SymbolResolver(etoro_client)
        instrument_id = await resolver.resolve(user_id, "BTCUSDT")   # -> 100000
    """

    def __init__(
        self,
        etoro_client: EtoroHttpClient,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self._client = etoro_client
        self._ttl = cache_ttl_seconds
        # Cache format: { "symbolFull": { "instrumentId": int, "displayname": str } }
        self._catalogue: Optional[dict[str, dict[str, Any]]] = None
        self._catalogue_loaded_at: float = 0.0

    async def resolve(self, user_id: str, symbol: str) -> Optional[int]:
        """Resolve a user-facing symbol to an eToro instrument ID (or None)."""
        if not symbol or not symbol.strip():
            return None

        # 1. Static alias map
        norm = _normalize_symbol(symbol)
        aliased = SYMBOL_ALIASES.get(norm)
        if aliased:
            inst = await self._find_in_catalogue(user_id, aliased)
            if inst is not None:
                return inst
            # If the alias is not in the catalogue (unlikely), fall through.

        # 2. Heuristic: strip exchange suffix (BTCUSDT -> BTC)
        base = _strip_exchange_suffix(norm)
        if base and base != norm:
            inst = await self._find_in_catalogue(user_id, base)
            if inst is not None:
                return inst

        # 3. Exact match on normalized symbol
        inst = await self._find_in_catalogue(user_id, norm)
        if inst is not None:
            return inst

        logger.warning("Could not resolve symbol '%s' to an eToro instrument", symbol)
        return None

    async def _find_in_catalogue(self, user_id: str, canonical: str) -> Optional[int]:
        """Find ``canonical`` (symbolFull) in the cached eToro catalogue."""
        catalogue = await self._get_catalogue(user_id)
        if not catalogue:
            return None

        # Exact match on symbolFull
        entry = catalogue.get(canonical.upper())
        if entry is not None:
            return entry["instrumentId"]

        # Exact match on displayname (e.g. "EUR/USD" -> eurusd entry)
        canonical_norm = canonical.lower().replace("/", "")
        for sym_full, meta in catalogue.items():
            display_norm = meta["displayname"].lower().replace("/", "")
            if display_norm == canonical_norm:
                return meta["instrumentId"]

        return None

    async def _get_catalogue(self, user_id: str) -> dict[str, dict[str, Any]]:
        """Fetch (and cache) the full eToro instrument catalogue."""
        now = time.monotonic()
        if self._catalogue is not None and (now - self._catalogue_loaded_at) < self._ttl:
            return self._catalogue

        try:
            result = await self._client.search_instruments(
                user_id=user_id,
                query="all",
                fields="instrumentId,internalSymbolFull,displayname",
            )
            instruments = (
                result.get("instrumentDisplayDatas")
                or result.get("InstrumentDisplayDatas")
                or result.get("items")
                or result.get("Items")
                or []
            )
            if isinstance(instruments, dict):
                instruments = [instruments]

            catalogue: dict[str, dict[str, Any]] = {}
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
                if inst_id is not None and symbol_full:
                    catalogue[str(symbol_full).upper()] = {
                        "instrumentId": int(inst_id),
                        "displayname": str(display_name),
                    }

            if not catalogue:
                logger.error("eToro instrument catalogue is empty")
                return {}

            self._catalogue = catalogue
            self._catalogue_loaded_at = now
            logger.info("Loaded eToro instrument catalogue: %d instruments", len(catalogue))
            return catalogue
        except Exception as e:
            logger.error("Failed to load eToro instrument catalogue: %s", e)
            # If we have a stale cache, keep using it
            if self._catalogue is not None:
                return self._catalogue
            return {}

    def invalidate_cache(self) -> None:
        """Force a fresh catalogue download on the next resolve()."""
        self._catalogue = None
        self._catalogue_loaded_at = 0.0