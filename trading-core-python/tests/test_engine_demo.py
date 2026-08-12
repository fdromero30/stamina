"""Tests for demo-account handling in the trading engine."""
import asyncio
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.bot.engine import TradingBotEngine
from app.settings import settings


class _Signal:
    def __init__(self):
        self.action = mock.MagicMock(value="BUY")
        self.units = 10.0
        self.entry_price = 1.1000
        self.stop_loss = 1.0950
        self.take_profit = 1.1100
        self.order_type = "market"
        self.limit_price = None


def _execute_with_mock():
    """Run _execute_trade with a mocked AsyncClient; return the POST call."""
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"status": "success", "positionId": 1234, "message": "ok"}

    ctx = mock.Mock()
    ctx.__aenter__ = mock.AsyncMock(return_value=ctx)
    ctx.__aexit__ = mock.AsyncMock(return_value=False)
    ctx.post = mock.AsyncMock(return_value=resp)

    engine = TradingBotEngine(
        strategies_client=mock.AsyncMock(),
        market_data_client=mock.AsyncMock(),
        etoro_http_client=mock.AsyncMock(),
        base_url="http://backend",
    )

    with mock.patch("app.bot.engine.httpx.AsyncClient") as cls:
        cls.return_value = ctx
        asyncio.run(engine._execute_trade("user-1", 100000, _Signal()))

    return ctx.post.call_args


def test_execute_trade_envia_demo_de_settings():
    original = settings.use_demo_account
    settings.use_demo_account = False
    try:
        call = _execute_with_mock()
        assert call.args[0] == "http://backend/orders/execute-smart"
        assert call.kwargs["json"]["demo"] is False
    finally:
        settings.use_demo_account = original


def test_execute_trade_demo_true_por_defecto_settings():
    original = settings.use_demo_account
    settings.use_demo_account = True
    try:
        call = _execute_with_mock()
        assert call.kwargs["json"]["demo"] is True
    finally:
        settings.use_demo_account = original