from app.integrations.etoro_client import EtoroClient, OrderRequest


class TradingBotEngine:
    def __init__(self, broker: EtoroClient) -> None:
        self._broker = broker

    async def run_dry_signal(self) -> dict[str, object]:
        return {
            "mode": "dry_run",
            "signal": {
                "symbol": "AAPL",
                "side": "buy",
                "units": 1,
                "confidence": 0.0,
            },
            "order_submitted": False,
        }

    async def submit_market_order(self, symbol: str, side: str, units: float) -> dict[str, object]:
        order = OrderRequest(symbol=symbol, side=side, units=units)
        return await self._broker.place_order(order)

