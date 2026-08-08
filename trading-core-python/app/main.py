"""FastAPI application for the Staminia Trading Core."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.bot import persistence
from app.bot.engine import TradingBotEngine
from app.bot.scheduler import TradingScheduler
from app.bot.signals import compute_sma
from app.integrations.market_data_client import MarketDataClient
from app.integrations.orders_client import EtoroHttpClient, HttpOrdersClient, OrderRequest
from app.integrations.strategies_client import StrategiesClient
from app.settings import settings

# Initialize the persistence database
persistence.init_db()

logger = logging.getLogger(__name__)

# ── Clients ─────────────────────────────────────────────────────────────

base_url = settings.users_config_api_url
strategies_client = StrategiesClient(base_url=base_url)
market_data_client = MarketDataClient(base_url=base_url)
etoro_http_client = EtoroHttpClient(base_url=base_url)

engine = TradingBotEngine(
    strategies_client=strategies_client,
    market_data_client=market_data_client,
    etoro_http_client=etoro_http_client,
    base_url=base_url,
)

scheduler = TradingScheduler(interval_seconds=settings.trading_interval_seconds)
scheduler.set_tick_handler(engine.run_trading_cycle)

app = FastAPI(title="Stamina Trading Core", version="0.2.0")


# ── Health ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "service": "trading-core",
        "status": "ok",
        "version": "0.2.0",
    }


# ── Chart Data ──────────────────────────────────────────────────────────


async def _resolve_symbol_instrument_id(user_id: str, symbol: str) -> Optional[int]:
    """Resolve an eToro instrument ID from a symbol using the search endpoint.

    eToro uses negative instrument IDs for forex pairs (e.g. EUR/USD = -100000),
    so we must NOT filter them out.  We also try several search queries because
    the eToro search endpoint can be inconsistent about matching.
    """
    # Normalize the symbol for matching (e.g. "EUR/USD" -> "eurusd")
    symbol_lower = symbol.lower().replace("/", "")

    # Try progressively more specific queries
    queries = [symbol, symbol_lower, symbol.replace("/", "")]
    for query in queries:
        try:
            result = await etoro_http_client.search_instruments(
                user_id=user_id,
                query=query,
                fields="instrumentId,internalSymbolFull,displayname",
            )
            # eToro /market-data/instruments response format:
            # { "instrumentDisplayDatas": [ { "instrumentID": 1, "instrumentDisplayName": "EUR/USD",
            #     "symbolFull": "EURUSD", ... } ] }
            # Also handle the legacy /market-data/search format:
            # { "items": [ { "instrumentId": ..., "internalSymbolFull": ..., "displayname": ... } ] }
            instruments = (
                result.get("instrumentDisplayDatas")
                or result.get("InstrumentDisplayDatas")
                or result.get("items")
                or result.get("Items")
                or result.get("instruments")
                or result.get("Instruments")
                or []
            )
            if isinstance(instruments, dict):
                instruments = [instruments]

            # Normalize field names (eToro uses camelCase).  Keep ALL instruments,
            # including negative IDs (forex pairs).
            normalized = []
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
                if inst_id is not None:
                    normalized.append({
                        "instrumentId": int(inst_id),
                        "internalSymbolFull": str(symbol_full),
                        "displayname": str(display_name),
                    })

            if not normalized:
                continue

            # Try to find an exact match for the symbol (e.g. "EUR/USD")
            for inst in normalized:
                full = inst["internalSymbolFull"].lower().replace("/", "")
                display = inst["displayname"].lower()
                if symbol_lower in full or symbol_lower in display or "eurusd" in full:
                    return inst["instrumentId"]

            # If we found instruments but no exact match, keep the first one
            # as a fallback for this query attempt.
            logger.warning("No exact match for %s in query '%s', using first result: %s",
                           symbol, query, normalized[0])
            return normalized[0]["instrumentId"]
        except Exception as e:
            logger.warning("Search query '%s' failed for %s: %s", query, symbol, e)
            continue

    logger.error("Failed to resolve instrument ID for %s after all search attempts", symbol)
    return None


def _parse_timestamp(ts: Optional[str]) -> Optional[str]:
    """Normalize a candle timestamp to an ISO-8601 string if possible."""
    if not ts:
        return None
    # eToro sometimes returns Unix milliseconds
    try:
        if ts.isdigit() and len(ts) >= 13:
            return datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).isoformat()
        if ts.isdigit() and len(ts) == 10:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        pass
    return ts


@app.get("/chart/eurusd")
async def chart_eurusd(
    userId: str,
    interval: str = "5m",
    count: int = 300,
) -> dict[str, Any]:
    """
    Return EUR/USD chart data for the Strategy Chart dashboard.

    Includes:
    - Historical candles (OHLC + timestamp)
    - MA9 and MA200 series
    - Current bid/ask (last price)
    """
    symbol = "EUR/USD"

    # 1. Resolve instrument ID
    instrument_id = await _resolve_symbol_instrument_id(userId, symbol)
    if instrument_id is None:
        raise HTTPException(status_code=404, detail=f"Cannot resolve symbol {symbol}")

    # 2. Fetch candles
    candles = await market_data_client.get_candles(
        user_id=userId,
        instrument_id=instrument_id,
        interval=interval,
        count=count,
    )
    if not candles:
        raise HTTPException(status_code=502, detail="No candle data received from eToro")

    # 3. Fetch current rates
    rates = await market_data_client.get_rates(userId, [instrument_id])
    last_bid: Optional[float] = None
    last_ask: Optional[float] = None
    if rates:
        last_bid = rates[0].bid
        last_ask = rates[0].ask

    # 4. Build candle + MA series for the chart
    closes = [c.close for c in candles]
    ma9 = compute_sma(closes, settings.default_ma_short)
    ma200 = compute_sma(closes, settings.default_ma_long)

    # Build MA series aligned to candle timestamps
    ma9_series: list[dict[str, Any]] = []
    ma200_series: list[dict[str, Any]] = []

    # MA9: first valid value appears at index (ma_short_period - 1)
    ma9_offset = settings.default_ma_short - 1
    for i, val in enumerate(ma9):
        idx = i + ma9_offset
        if idx < len(candles):
            ts = _parse_timestamp(candles[idx].timestamp)
            ma9_series.append({
                "time": ts or candles[idx].timestamp or f"idx-{idx}",
                "value": round(val, 5),
            })

    # MA200: first valid value appears at index (ma_long_period - 1)
    ma200_offset = settings.default_ma_long - 1
    for i, val in enumerate(ma200):
        idx = i + ma200_offset
        if idx < len(candles):
            ts = _parse_timestamp(candles[idx].timestamp)
            ma200_series.append({
                "time": ts or candles[idx].timestamp or f"idx-{idx}",
                "value": round(val, 5),
            })

    # 5. Build candle series
    candle_series: list[dict[str, Any]] = []
    for c in candles:
        ts = _parse_timestamp(c.timestamp)
        candle_series.append({
            "time": ts or c.timestamp or "",
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
        })

    return {
        "symbol": symbol,
        "instrument_id": instrument_id,
        "interval": interval,
        "candles": candle_series,
        "ma9": ma9_series,
        "ma200": ma200_series,
        "last_price": {
            "bid": last_bid,
            "ask": last_ask,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Bot Control ─────────────────────────────────────────────────────────


@app.post("/bot/start")
async def start_bot() -> dict[str, object]:
    """Start the automated trading scheduler."""
    try:
        await scheduler.start()
        persistence.save_bot_state("running", True)
        return {
            "status": "started",
            "interval_seconds": scheduler.interval_seconds,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/bot/stop")
async def stop_bot() -> dict[str, object]:
    """Stop the automated trading scheduler."""
    await scheduler.stop()
    persistence.save_bot_state("running", False)
    return {
        "status": "stopped",
        "cycles_completed": scheduler.cycle_count,
    }


@app.get("/bot/status")
async def bot_status() -> dict[str, object]:
    """Get the current status of the trading scheduler."""
    return {
        "running": scheduler.is_running,
        "interval_seconds": scheduler.interval_seconds,
        "cycles_completed": scheduler.cycle_count,
        "last_run": scheduler.last_run.isoformat() if scheduler.last_run else None,
        "next_run": scheduler.next_run.isoformat() if scheduler.next_run else None,
    }


@app.get("/bot/cycles")
async def bot_cycles() -> dict[str, object]:
    """Get the recent cycle history and open positions for observability."""
    return {
        "cycles": scheduler.cycle_history,
        "open_positions": engine.open_positions,
    }


@app.post("/bot/cycle")
async def trigger_cycle() -> dict[str, object]:
    """Manually trigger a single trading cycle (for testing)."""
    try:
        result = await scheduler.trigger_cycle()
        return {
            "status": "completed",
            "result": result,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/bot/evaluate/{strategy_id}")
async def evaluate_strategy(strategy_id: str) -> dict[str, object]:
    """Evaluate a specific strategy without executing any trades."""
    result = await engine.evaluate_strategy(strategy_id)
    return result


# ── Legacy Endpoints (kept for backward compatibility) ──────────────────


class OrderPayload(BaseModel):
    symbol: str = Field(min_length=1, examples=["AAPL"])
    side: str = Field(pattern="^(buy|sell)$", examples=["buy"])
    units: float = Field(gt=0, examples=[1])


@app.post("/bot/dry-run")
async def dry_run() -> dict[str, object]:
    """Legacy dry-run endpoint. Returns a placeholder signal."""
    return {
        "mode": "dry_run",
        "signal": {
            "symbol": "EUR/USD",
            "side": "hold",
            "units": 0,
            "confidence": 0.0,
        },
        "order_submitted": False,
    }


@app.post("/orders/market")
async def submit_market_order(payload: OrderPayload) -> dict[str, object]:
    """Submit a market order via the Java backend."""
    orders_client = HttpOrdersClient(base_url=base_url)
    order = OrderRequest(
        user_id="00000000-0000-0000-0000-000000000000",
        symbol=payload.symbol,
        side=payload.side,
        units=payload.units,
    )
    return await orders_client.place_order(order)
