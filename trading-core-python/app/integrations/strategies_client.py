"""HTTP client for fetching strategy configurations from the Java backend."""

from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass(frozen=True)
class StrategyConfigDTO:
    """Strategy configuration as returned by the Java backend (GET /strategies)."""
    id: str
    user_id: str
    user_display_name: str
    name: str
    symbol: str
    max_position_size: Optional[float]
    enabled: bool
    max_drawdown: Optional[float]
    max_risk_per_trade: Optional[float]
    max_daily_loss: Optional[float]
    max_open_positions: Optional[int]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    spread_threshold: Optional[float]
    trading_window_start: Optional[str]
    trading_window_end: Optional[str]
    trailing_stop_activation: Optional[float]
    break_even_trigger: Optional[float]
    use_ml: bool
    ml_strategy_code: Optional[str]
    # Transversal risk management (máquina de estados + trailing ATR)
    hito1_trigger_r: Optional[float] = None
    hito2_trigger_r: Optional[float] = None
    hito2_sl_r: Optional[float] = None
    breakeven_spread_mult: Optional[float] = None
    trailing_enabled: Optional[bool] = None
    trailing_atr_mult: Optional[float] = None
    max_tp_far_r: Optional[float] = None
    use_candle_high_low: Optional[bool] = None
    sl_update_retry_seconds: Optional[int] = None
    min_sl_update_spacing_pips: Optional[float] = None


class StrategiesClient:
    """Fetches strategy configurations from the Java backend."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def get_strategies(self, user_id: Optional[str] = None) -> list[StrategyConfigDTO]:
        """Fetch all strategies, optionally filtered by userId."""
        params: dict[str, str] = {}
        if user_id is not None:
            params["userId"] = user_id

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._base_url}/strategies",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, list):
            return []

        return [self._parse_strategy(item) for item in data]

    async def get_strategy(self, strategy_id: str) -> Optional[StrategyConfigDTO]:
        """Fetch a single strategy by ID."""
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/strategies/{strategy_id}",
                )
                response.raise_for_status()
                return self._parse_strategy(response.json())
            except httpx.HTTPStatusError:
                return None

    def _parse_strategy(self, item: dict[str, Any]) -> StrategyConfigDTO:
        return StrategyConfigDTO(
            id=str(item.get("id", "")),
            user_id=str(item.get("userId", "")),
            user_display_name=str(item.get("userDisplayName", "")),
            name=str(item.get("name", "")),
            symbol=str(item.get("symbol", "")),
            max_position_size=_to_float(item.get("maxPositionSize")),
            enabled=bool(item.get("enabled", False)),
            max_drawdown=_to_float(item.get("maxDrawdown")),
            max_risk_per_trade=_to_float(item.get("maxRiskPerTrade")),
            max_daily_loss=_to_float(item.get("maxDailyLoss")),
            max_open_positions=_to_int(item.get("maxOpenPositions")),
            stop_loss=_to_float(item.get("stopLoss")),
            take_profit=_to_float(item.get("takeProfit")),
            spread_threshold=_to_float(item.get("spreadThreshold")),
            trading_window_start=item.get("tradingWindowStart"),
            trading_window_end=item.get("tradingWindowEnd"),
            trailing_stop_activation=_to_float(item.get("trailingStopActivation")),
            break_even_trigger=_to_float(item.get("breakEvenTrigger")),
            use_ml=bool(item.get("useML", False)),
            ml_strategy_code=item.get("mlStrategyCode"),
            hito1_trigger_r=_to_float(item.get("hito1TriggerR")),
            hito2_trigger_r=_to_float(item.get("hito2TriggerR")),
            hito2_sl_r=_to_float(item.get("hito2SlR")),
            breakeven_spread_mult=_to_float(item.get("breakevenSpreadMult")),
            trailing_enabled=_to_bool(item.get("trailingEnabled")),
            trailing_atr_mult=_to_float(item.get("trailingAtrMult")),
            max_tp_far_r=_to_float(item.get("maxTpFarR")),
            use_candle_high_low=_to_bool(item.get("useCandleHighLow")),
            sl_update_retry_seconds=_to_int(item.get("slUpdateRetrySeconds")),
            min_sl_update_spacing_pips=_to_float(item.get("minSlUpdateSpacingPips")),
        )


def _to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _to_bool(value: object) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    try:
        return bool(int(value))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None
