from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.bot.engine import TradingBotEngine
from app.integrations.orders_client import HttpOrdersClient
from app.settings import settings

orders_client = HttpOrdersClient(base_url=settings.users_config_api_url)
engine = TradingBotEngine(orders_client=orders_client)

app = FastAPI(title="Stamina Trading Core", version="0.1.0")


class OrderPayload(BaseModel):
    symbol: str = Field(min_length=1, examples=["AAPL"])
    side: str = Field(pattern="^(buy|sell)$", examples=["buy"])
    units: float = Field(gt=0, examples=[1])


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "service": "trading-core",
        "status": "ok",
    }


@app.post("/bot/dry-run")
async def dry_run() -> dict[str, object]:
    return await engine.run_dry_signal()


@app.post("/orders/market")
async def submit_market_order(payload: OrderPayload) -> dict[str, object]:
    return await engine.submit_market_order(
        symbol=payload.symbol,
        side=payload.side,
        units=payload.units,
    )

