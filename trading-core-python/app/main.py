"""FastAPI application for the Staminia Trading Core."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.bot import persistence
from app.bot.engine import TradingBotEngine
from app.bot.scheduler import TradingScheduler
from app.bot.signals import compute_sma
from app.integrations.market_data_client import MarketDataClient
from app.integrations.orders_client import EtoroHttpClient, HttpOrdersClient, OrderRequest
from app.integrations.strategies_client import StrategiesClient
from app.integrations.symbol_resolver import SymbolResolver
from app.settings import settings

# Initialize the persistence database
persistence.init_db()

logger = logging.getLogger(__name__)

# ── Clients ─────────────────────────────────────────────────────────────

base_url = settings.users_config_api_url
strategies_client = StrategiesClient(base_url=base_url)
market_data_client = MarketDataClient(base_url=base_url)
etoro_http_client = EtoroHttpClient(base_url=base_url)

# Shared symbol resolver (used by both the chart endpoint and the bot engine)
symbol_resolver = SymbolResolver(etoro_http_client)

engine = TradingBotEngine(
    strategies_client=strategies_client,
    market_data_client=market_data_client,
    etoro_http_client=etoro_http_client,
    base_url=base_url,
)
# Reuse the shared resolver so chart + bot share the same instrument catalogue cache.
engine.symbol_resolver = symbol_resolver

scheduler = TradingScheduler(interval_seconds=settings.trading_interval_seconds)
scheduler.set_tick_handler(engine.run_trading_cycle)

app = FastAPI(title="Stamina Trading Core", version="0.2.0")

# CORS para localhost y Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "service": "trading-core",
        "status": "ok",
        "version": "0.2.0",
    }


# ── Chart Data ──────────────────────────────────────────────────────────


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


def _get_engine_state() -> dict[str, Any]:
    """
    Gather the deterministic state of the trading engine for observability.

    This lets the chart (and the UI) show the engine's accumulated state
    since it started running: whether it is running, when it started, how
    many cycles it has completed, the open positions and the last signal
    that was evaluated.
    """
    started_at = persistence.load_bot_state("engine_started_at")
    last_evaluation: Optional[dict[str, Any]] = None

    # Walk the cycle history (most recent first) to find the last evaluation
    # that produced a signal.
    for cycle in scheduler.cycle_history:
        evaluations = cycle.get("evaluations") or []
        if evaluations:
            last_evaluation = evaluations[0]
            break

    return {
        "running": scheduler.is_running,
        "started_at": started_at,
        "cycle_count": scheduler.cycle_count,
        "last_run": scheduler.last_run.isoformat() if scheduler.last_run else None,
        "next_run": scheduler.next_run.isoformat() if scheduler.next_run else None,
        "open_positions": engine.open_positions,
        "last_evaluation": last_evaluation,
    }


@app.get("/chart/{symbol:path}")
async def chart_data(
    symbol: str,
    userId: str,
    interval: str = "5m",
    count: int = 300,
) -> dict[str, Any]:
    """
    Return chart data for any symbol (e.g. EUR/USD, BTC, ETH) for the
    Strategy Chart dashboard.

    Includes:
    - Historical candles (OHLC + timestamp)
    - MA9 and MA200 series
    - Current bid/ask (last price)
    - Engine state (running, started_at, open positions, last evaluation)
    """
    # 1. Resolve instrument ID (shared resolver with alias map + cached catalogue)
    instrument_id = await symbol_resolver.resolve(userId, symbol)
    if instrument_id is None:
        # The 404 here is almost always NOT about the symbol itself — it is
        # an upstream failure retrieving the instrument catalogue (missing
        # eToro API key, backend down, etc).  Surface that clearly instead
        # of the misleading "Cannot resolve symbol".
        upstream_error = getattr(symbol_resolver, "last_error", None)
        if upstream_error and "No eToro API key" in upstream_error:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No eToro API key configured for user {userId}. "
                    "Add an eToro API key in the API Keys page before loading charts."
                ),
            )
        if upstream_error and "Failed to load eToro instrument catalogue" in upstream_error:
            raise HTTPException(
                status_code=502,
                detail=f"Could not reach the eToro instrument catalogue: {upstream_error}",
            )
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
        "engine": _get_engine_state(),
    }


# ── Bot Control ─────────────────────────────────────────────────────────


@app.post("/bot/start")
async def start_bot() -> dict[str, object]:
    """Start the automated trading scheduler."""
    try:
        await scheduler.start()
        now_iso = datetime.now(timezone.utc).isoformat()
        persistence.save_bot_state("running", True)
        persistence.save_bot_state("engine_started_at", now_iso)
        return {
            "status": "started",
            "interval_seconds": scheduler.interval_seconds,
            "started_at": now_iso,
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
    # Estrategia activa (real o default EUR/USD)
    strategy = await engine.get_active_strategy()
    # Próximo blackout por noticias High de EUR/USD (desde la caché local)
    next_blackout = None
    try:
        upcoming = engine.news_client.next_upcoming_event(datetime.now(timezone.utc))
        if upcoming is not None:
            next_blackout = {
                "title": upcoming.title,
                "country": upcoming.country,
                "event_time": upcoming.event_time_utc.isoformat(),
                "impact": upcoming.impact,
            }
    except Exception:
        logger.warning("Failed to resolve next blackout for status", exc_info=True)
    return {
        "running": scheduler.is_running,
        "interval_seconds": scheduler.interval_seconds,
        "cycles_completed": scheduler.cycle_count,
        "last_run": scheduler.last_run.isoformat() if scheduler.last_run else None,
        "next_run": scheduler.next_run.isoformat() if scheduler.next_run else None,
        "strategy": strategy,
        "run_id": getattr(scheduler, "_run_id", None),
        "next_blackout": next_blackout,
    }


@app.get("/bot/cycles")
async def bot_cycles() -> dict[str, object]:
    """Get the recent executions (runs) with their cycles and open positions."""
    runs = persistence.load_runs(limit=10)
    runs_with_cycles = []
    for run in runs:
        cycles = persistence.load_cycles_by_run(run["id"], limit=100)
        runs_with_cycles.append({**run, "cycles": cycles})
    return {
        "runs": runs_with_cycles,
        "recent_cycles": scheduler.cycle_history,
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
