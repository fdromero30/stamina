"""FastAPI application for the Staminia Trading Core."""

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.bot.engine import TradingBotEngine
from app.bot.scheduler import TradingScheduler
from app.integrations.market_data_client import MarketDataClient
from app.integrations.orders_client import EtoroHttpClient, HttpOrdersClient
from app.integrations.strategies_client import StrategiesClient
from app.settings import settings

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


# ── Bot Control ─────────────────────────────────────────────────────────


@app.post("/bot/start")
async def start_bot() -> dict[str, object]:
    """Start the automated trading scheduler."""
    try:
        await scheduler.start()
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
    order = type("OrderRequest", (), {
        "user_id": "00000000-0000-0000-0000-000000000000",
        "symbol": payload.symbol,
        "side": payload.side,
        "units": payload.units,
    })()
    return await orders_client.place_order(order)