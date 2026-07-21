from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class OrderRequest:
    user_id: str
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
                    "userId": order.user_id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "units": order.units,
                },
            )
            response.raise_for_status()
            return response.json()


class EtoroHttpClient:
    """Direct HTTP client to the eToro proxy endpoints exposed by users-config-backend.

    Each method requires a ``userId`` so the backend can resolve the user's
    encrypted eToro credentials from the database.
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    # ── Market Data ──────────────────────────────────────────────────

    async def search_instruments(
        self, user_id: str, query: str, fields: str = "instrumentId,internalSymbolFull,displayname"
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/etoro/market-data/search",
                params={"userId": user_id, "q": query, "fields": fields},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_rates(self, user_id: str, instrument_ids: list[int]) -> dict[str, Any]:
        ids_str = ",".join(str(i) for i in instrument_ids)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/etoro/market-data/rates",
                params={"userId": user_id, "instrumentIds": ids_str},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_candles(
        self,
        user_id: str,
        instrument_id: int,
        direction: str = "desc",
        interval: str = "1h",
        count: int = 100,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/etoro/market-data/candles/{instrument_id}",
                params={
                    "userId": user_id,
                    "direction": direction,
                    "interval": interval,
                    "count": count,
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Trading – Demo ───────────────────────────────────────────────

    async def demo_open_by_amount(
        self,
        user_id: str,
        instrument_id: int,
        is_buy: bool,
        amount: float,
        leverage: int = 1,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/etoro/trading/demo/open-by-amount",
                params={
                    "userId": user_id,
                    "instrumentId": instrument_id,
                    "isBuy": is_buy,
                    "leverage": leverage,
                    "amount": amount,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def demo_open_by_units(
        self,
        user_id: str,
        instrument_id: int,
        is_buy: bool,
        units: float,
        leverage: int = 1,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/etoro/trading/demo/open-by-units",
                params={
                    "userId": user_id,
                    "instrumentId": instrument_id,
                    "isBuy": is_buy,
                    "leverage": leverage,
                    "units": units,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def demo_close_position(
        self, user_id: str, position_id: int, units_to_deduct: float | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"userId": user_id}
        if units_to_deduct is not None:
            params["unitsToDeduct"] = units_to_deduct
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/etoro/trading/demo/close-position/{position_id}",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Trading – Real ───────────────────────────────────────────────

    async def open_by_amount(
        self,
        user_id: str,
        instrument_id: int,
        is_buy: bool,
        amount: float,
        leverage: int = 1,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/etoro/trading/open-by-amount",
                params={
                    "userId": user_id,
                    "instrumentId": instrument_id,
                    "isBuy": is_buy,
                    "leverage": leverage,
                    "amount": amount,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def open_by_units(
        self,
        user_id: str,
        instrument_id: int,
        is_buy: bool,
        units: float,
        leverage: int = 1,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/etoro/trading/open-by-units",
                params={
                    "userId": user_id,
                    "instrumentId": instrument_id,
                    "isBuy": is_buy,
                    "leverage": leverage,
                    "units": units,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def close_position(
        self, user_id: str, position_id: int, units_to_deduct: float | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"userId": user_id}
        if units_to_deduct is not None:
            params["unitsToDeduct"] = units_to_deduct
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/etoro/trading/close-position/{position_id}",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def cancel_order(
        self, user_id: str, order_id: int, demo: bool = False
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{self._base_url}/etoro/trading/cancel-order/{order_id}",
                params={"userId": user_id, "demo": str(demo).lower()},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Portfolio / P&L ──────────────────────────────────────────────

    async def get_portfolio(self, user_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/etoro/portfolio",
                params={"userId": user_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_demo_portfolio(self, user_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/etoro/portfolio/demo",
                params={"userId": user_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_real_pnl(self, user_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/etoro/portfolio/pnl",
                params={"userId": user_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_demo_pnl(self, user_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/etoro/portfolio/pnl/demo",
                params={"userId": user_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_trade_history(
        self, user_id: str, min_date: str, page: int = 1, page_size: int = 20
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base_url}/etoro/portfolio/trade-history",
                params={
                    "userId": user_id,
                    "minDate": min_date,
                    "page": page,
                    "pageSize": page_size,
                },
            )
            resp.raise_for_status()
            return resp.json()