from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    units: float
    order_type: str = "market"


class OrdersClient(ABC):
    """Abstract interface for order execution backends."""

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> dict:
        ...


class HttpOrdersClient(OrdersClient):
    """Executes orders via an HTTP backend (e.g. users-config-backend)."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def place_order(self, order: OrderRequest) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self._base_url}/orders/execute",
                json={
                    "symbol": order.symbol,
                    "side": order.side,
                    "units": order.units,
                },
            )
            response.raise_for_status()
            return response.json()