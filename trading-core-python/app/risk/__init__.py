"""Transversal risk management module — reusable by any trading strategy."""

from .models import (
    PositionRiskState,
    RiskManagementConfig,
    MarketSnapshot,
    RiskDecision,
)
from .state_machine import (
    compute_risk_from_price,
    effective_price,
    compute_breakeven_sl,
    compute_hito2_sl,
    compute_trailing_sl,
    evaluate,
)
from .position_risk_manager import PositionRiskManager

__all__ = [
    "PositionRiskState",
    "RiskManagementConfig",
    "MarketSnapshot",
    "RiskDecision",
    "compute_risk_from_price",
    "effective_price",
    "compute_breakeven_sl",
    "compute_hito2_sl",
    "compute_trailing_sl",
    "evaluate",
    "PositionRiskManager",
]