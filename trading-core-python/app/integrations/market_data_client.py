"""HTTP client for fetching market data from the Java backend (eToro proxy)."""

from typing import Any

import httpx

from app.bot.signals import Candle, MarketData

# ── eToro interval mapping ──────────────────────────────────────────────
# The eToro API expects named intervals (e.g. "FiveMinutes") in the URL path,
# not shorthand like "5m".  This map converts common shorthand formats to the
# values the eToro API accepts.
_ETORO_INTERVAL_MAP: dict[str, str] = {
    "1m": "OneMinute",
    "5m": "FiveMinutes",
    "10m": "TenMinutes",
    "15m": "FifteenMinutes",
    "30m": "ThirtyMinutes",
    "1h": "OneHour",
    "4h": "FourHours",
    "1d": "OneDay",
    "1w": "OneWeek",
}


def _to_etoro_interval(interval: str) -> str:
    """Convert a shorthand interval (e.g. ``5m``) to the eToro API format (e.g. ``FiveMinutes``).

    If the interval is already in eToro format or is not in the map, it is
    returned unchanged so that callers can pass eToro-native values directly.
    """
    return _ETORO_INTERVAL_MAP.get(interval, interval)


class MarketDataClient:
    """Fetches market data via the Java backend's eToro proxy endpoints."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def get_rates(
        self,
        user_id: str,
        instrument_ids: list[int],
    ) -> list[MarketData]:
        """
        Fetch current rates (bid/ask) for one or more instruments.

        GET /etoro/market-data/rates?userId={userId}&instrumentIds={ids}
        """
        if not instrument_ids:
            return []

        ids_str = ",".join(str(i) for i in instrument_ids)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._base_url}/etoro/market-data/rates",
                params={"userId": user_id, "instrumentIds": ids_str},
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_rates(data, instrument_ids)

    async def get_candles(
        self,
        user_id: str,
        instrument_id: int,
        interval: str = "5m",
        count: int = 300,
    ) -> list[Candle]:
        """
        Fetch historical candle data for an instrument.

        GET /etoro/market-data/candles/{instrumentId}?userId=&interval=&count=
        """
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._base_url}/etoro/market-data/candles/{instrument_id}",
                params={
                    "userId": user_id,
                    "direction": "desc",
                    "interval": _to_etoro_interval(interval),
                    "count": count,
                },
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_candles(data)

    def _parse_rates(
        self,
        data: dict[str, Any],
        instrument_ids: list[int],
    ) -> list[MarketData]:
        """
        Parse the rates response from eToro.
        The response format is typically:
        { "Rates": [ { "InstrumentID": ..., "Bid": ..., "Ask": ... }, ... ] }
        """
        rates_list: list[dict[str, Any]] = data.get("Rates") or data.get("rates") or []
        if isinstance(rates_list, dict):
            rates_list = [rates_list]

        result: list[MarketData] = []
        for rate in rates_list:
            inst_id = (
                rate.get("InstrumentID")
                or rate.get("instrumentId")
                or rate.get("instrumentID")
            )
            bid = rate.get("Bid") or rate.get("bid") or rate.get("BidRate")
            ask = rate.get("Ask") or rate.get("ask") or rate.get("AskRate")

            if inst_id is not None and bid is not None and ask is not None:
                result.append(MarketData(
                    bid=float(bid),
                    ask=float(ask),
                    instrument_id=int(inst_id),
                ))

        return result

    def _parse_candles(self, data: dict[str, Any]) -> list[Candle]:
        """
        Parse the candles response from eToro.

        The eToro API returns candles in a nested structure:
        { "candles": [ { "instrumentId": ..., "candles": [ { "open": ...,
            "high": ..., "low": ..., "close": ..., "fromDate": "..." }, ... ] } ] }

        Some proxies may return a flat structure instead:
        { "Candles": [ { "Open": ..., "High": ..., "Low": ..., "Close": ...,
                         "FromDate": "...", "FromDateISO": "..." }, ... ] }

        Note: candles are returned in descending order (most recent first).
        """
        # Handle the nested eToro structure: { "candles": [ { "candles": [...] } ] }
        candles_list: list[dict[str, Any]] = data.get("Candles") or data.get("candles") or []
        if isinstance(candles_list, dict):
            candles_list = [candles_list]

        # If the top-level list contains nested "candles" arrays, flatten them
        flattened: list[dict[str, Any]] = []
        for entry in candles_list:
            nested = entry.get("Candles") or entry.get("candles")
            if isinstance(nested, list):
                flattened.extend(nested)
            else:
                # Flat entry (already a candle)
                flattened.append(entry)

        # eToro returns candles in descending order; reverse to ascending
        flattened.reverse()

        result: list[Candle] = []
        for c in flattened:
            open_ = c.get("Open") or c.get("open")
            high = c.get("High") or c.get("high")
            low = c.get("Low") or c.get("low")
            close = c.get("Close") or c.get("close")

            # Extract timestamp (eToro may provide several field names)
            timestamp = (
                c.get("FromDateISO")
                or c.get("fromDateISO")
                or c.get("FromDate")
                or c.get("fromDate")
                or c.get("DateTime")
                or c.get("dateTime")
                or c.get("StartTime")
                or c.get("startTime")
                or c.get("Timestamp")
                or c.get("timestamp")
            )

            if open_ is not None and high is not None and low is not None and close is not None:
                result.append(Candle(
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    timestamp=str(timestamp) if timestamp is not None else None,
                ))

        return result