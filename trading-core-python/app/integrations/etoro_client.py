from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    units: float
    order_type: str = "market"


class EtoroClient:
    def __init__(self, base_url: str, api_key: str, account_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._account_id = account_id

    async def health(self) -> dict[str, str]:
        if self._api_key == "replace_me":
            return {"status": "not_configured", "broker": "etoro"}
        return {"status": "configured", "broker": "etoro"}

    async def place_order(self, order: OrderRequest) -> dict[str, object]:
        # Replace this adapter once official eToro API credentials and endpoints are confirmed.
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self._base_url}/accounts/{self._account_id}/orders",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=order.__dict__,
            )
            response.raise_for_status()
            return response.json()

