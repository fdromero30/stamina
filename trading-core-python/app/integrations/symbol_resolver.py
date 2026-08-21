"""Resolve user-facing symbols (BTCUSD, EUR/USD, BTCUSDT, ...) to eToro instrument IDs.

The eToro ``/market-data/instruments`` endpoint returns the FULL universe of
instruments (16k+) regardless of ``searchText``, so we must match the requested
symbol ourselves.  This resolver uses three layers, in order:

1. Static alias map    — fast, no network (BTC/USD -> BTC, XAUUSD -> XAUUSD, ...)
2. Heuristic normalize — strip exchange suffixes (USDT, USDC, PERP) and slashes
3. Cached catalogue    — download the full instrument list once (TTL 1h) and
                         match exact symbolFull/displayname, then substring

IMPORTANT (2026-08): The static instrument-ID fast path was REMOVED — the
hardcoded IDs (0, 1, 2, ..., 100000, 100001) are NOT the real eToro instrument
IDs and caused HTTP 500 on every candles/rates request for EUR/USD, BTC, ETH,
etc.  The eToro Public API uses instrument IDs that must come from the
``/market-data/instruments`` catalogue (forex pairs use NEGATIVE IDs, e.g.
EUR/USD is around -1xx, NOT +1).  Resolving through the cached catalogue is
the only reliable path.
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
    # Metals — eToro's instrument catalogue uses "GOLD" (instrumentID 18,
    # symbolFull "GOLD", displayname "Gold (Non Expiry)"), NOT "XAUUSD".
    "XAUUSD": "GOLD",
    "XAU/USD": "GOLD",
    "GOLD": "GOLD",
    "XAGUSD": "SILVER",
    "XAG/USD": "SILVER",
    "SILVER": "SILVER",
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


class SymbolResolver:
    """Shared resolver that maps user symbols to eToro instrument IDs.

    Usage::

        resolver = SymbolResolver(etoro_client)
        instrument_id = await resolver.resolve(user_id, "BTCUSDT")   # -> real eToro ID
    """

    def __init__(
        self,
        etoro_client: EtoroHttpClient,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self._client = etoro_client
        self._ttl = cache_ttl_seconds
        # Cache format: { "symbolFull": { "instrumentId": int, "displayname": str, "instrumentTypeID": int } }
        self._catalogue: Optional[dict[str, dict[str, Any]]] = None
        self._catalogue_loaded_at: float = 0.0
        # Cache of per-user instrument catalogues: { user_id: catalogue }
        # Different eToro API keys can see different instrument universes.
        self._per_user_catalogues: dict[str, dict[str, dict[str, Any]]] = {}
        self._per_user_loaded_at: dict[str, float] = {}
        # Human-readable error from the last failed catalogue fetch (cleared
        # on success).  Callers can inspect this to give a better error to
        # the end user.
        self.last_error: Optional[str] = None

    async def resolve(self, user_id: str, symbol: str) -> Optional[int]:
        """Resolve a user-facing symbol to an eToro instrument ID (or None).

        Always resolves through the cached eToro instrument catalogue — the
        static-ID fast path was removed because hardcoded IDs (0, 1, 100000,
        100001, ...) do not match the real eToro instrument IDs and caused
        HTTP 500 on every candles/rates request.

        Returns the instrument ID on success, or None if the symbol could not
        be resolved.  Callers can inspect ``self.last_error`` to get a
        human-readable reason for the failure.
        """
        if not symbol or not symbol.strip():
            return None

        norm = _normalize_symbol(symbol)

        # 1. Static alias map (via catalogue)
        aliased = SYMBOL_ALIASES.get(norm)
        if aliased is not None:
            inst = await self._find_in_catalogue(user_id, aliased)
            if inst is not None:
                return inst

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

        # 4. Substring match on displayname (e.g. "USD/JPY" vs "JPY/USD")
        inst = await self._find_substring_in_catalogue(user_id, norm)
        if inst is not None:
            return inst

        logger.warning("Could not resolve symbol '%s' to an eToro instrument", symbol)
        return None

    async def _find_in_catalogue(self, user_id: str, canonical: str) -> Optional[int]:
        """Find ``canonical`` (symbolFull) in the cached eToro catalogue."""
        catalogue = await self._get_catalogue(user_id)
        if not catalogue:
            return None

        canonical_upper = canonical.upper()
        canonical_norm = canonical.lower().replace("/", "")

        # 1. Exact match on symbolFull
        entry = catalogue.get(canonical_upper)
        if entry is not None:
            return entry["instrumentId"]

        # 2. Exact match on displayname (e.g. "EUR/USD" -> eurusd entry)
        for sym_full, meta in catalogue.items():
            display_norm = meta["displayname"].lower().replace("/", "")
            if display_norm == canonical_norm:
                return meta["instrumentId"]

        # 3. Prefix match on symbolFull — eToro sometimes appends a suffix
        #    (e.g. "EURUSD.N", "EURUSD.CFD", "EURUSD_1") to the canonical
        #    symbolFull.  Match the shortest entry that starts with the
        #    canonical symbol so we pick the base/spot instrument.
        prefix_matches: list[tuple[int, str]] = []
        for sym_full, meta in catalogue.items():
            sym_upper = str(sym_full).upper()
            if sym_upper.startswith(canonical_upper):
                prefix_matches.append((len(sym_upper), sym_upper))
        if prefix_matches:
            prefix_matches.sort(key=lambda t: t[0])
            shortest = prefix_matches[0][1]
            return catalogue[shortest]["instrumentId"]

        # 4. Prefix match on displayname (e.g. "EUR/USD" -> "EUR/USD (Non Expiry)")
        for sym_full, meta in catalogue.items():
            display_norm = meta["displayname"].lower().replace("/", "")
            if display_norm.startswith(canonical_norm):
                return meta["instrumentId"]

        return None

    async def _find_substring_in_catalogue(self, user_id: str, canonical: str) -> Optional[int]:
        """Substring match on displayname for symbols like GOLD, SILVER, etc."""
        catalogue = await self._get_catalogue(user_id)
        if not catalogue:
            return None

        target = canonical.lower().replace("/", "")
        for sym_full, meta in catalogue.items():
            display_norm = meta["displayname"].lower().replace("/", "")
            full_norm = sym_full.lower().replace("/", "")
            if target in display_norm or target in full_norm:
                return meta["instrumentId"]

        return None

    async def _get_catalogue(self, user_id: str) -> dict[str, dict[str, Any]]:
        """
        Fetch (and cache per-user) the full eToro instrument catalogue.

        Each eToro API key sees its own instrument universe, so we cache the
        catalogue PER USER to avoid cross-user ID mismatches.

        On failure, sets ``self.last_error`` to a human-readable reason.
        """
        now = time.monotonic()
        cached = self._per_user_catalogues.get(user_id)
        loaded_at = self._per_user_loaded_at.get(user_id, 0.0)
        if cached is not None and (now - loaded_at) < self._ttl:
            self.last_error = None
            return cached

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
                        "instrumentTypeID": int(inst.get("instrumentTypeID") or 0)
                        if inst.get("instrumentTypeID") is not None
                        else None,
                    }

            if not catalogue:
                self.last_error = "eToro returned an empty instrument catalogue"
                logger.error("eToro instrument catalogue is empty for user %s", user_id)
                return {}

            self.last_error = None
            self._per_user_catalogues[user_id] = catalogue
            self._per_user_loaded_at[user_id] = now
            # Keep the shared global cache in sync for the chart endpoint
            self._catalogue = catalogue
            self._catalogue_loaded_at = now
            logger.info(
                "Loaded eToro instrument catalogue for user %s: %d instruments",
                user_id, len(catalogue),
            )
            return catalogue
        except Exception as e:
            msg = str(e)
            self.last_error = msg
            logger.error("Failed to load eToro instrument catalogue for user %s: %s", user_id, msg)
            # If we have a stale cache for this user, keep using it
            stale = self._per_user_catalogues.get(user_id)
            if stale is not None:
                return stale
            # Fall back to the shared global cache
            if self._catalogue is not None:
                return self._catalogue
            return {}

    def invalidate_cache(self) -> None:
        """Force a fresh catalogue download on the next resolve()."""
        self._catalogue = None
        self._catalogue_loaded_at = 0.0
        self._per_user_catalogues.clear()
        self._per_user_loaded_at.clear()