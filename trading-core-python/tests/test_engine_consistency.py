"""Tests for eToro-consistency behaviour in the engine (backoff, snapshot)."""
import asyncio
import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import sqlite3

from app.bot import persistence as P
from app.bot.engine import PortfolioSnapshot, TradingBotEngine
from app.bot.signals import Signal, SignalAction
from app.settings import settings


@pytest.fixture()
def engine():
    old_conn = P.db._conn
    old_atomic = P.db._in_atomic
    P.db._conn = sqlite3.connect(":memory:")
    P.db._conn.row_factory = sqlite3.Row
    P.db._in_atomic = False
    P.init_db()
    eng = TradingBotEngine(
        strategies_client=mock.AsyncMock(),
        market_data_client=mock.AsyncMock(),
        etoro_http_client=mock.AsyncMock(),
        base_url="http://backend",
    )
    yield eng
    try:
        P.db._conn.close()
    except Exception:
        pass
    P.db._conn = old_conn
    P.db._in_atomic = old_atomic


def test_portfolio_snapshot_counts_by_instrument():
    snap = PortfolioSnapshot(
        user_id="u1",
        available_balance=1000,
        positions=[
            {"instrumentID": 11, "positionID": 1, "isBuy": True},
            {"instrumentID": 11, "positionID": 2, "isBuy": False},
            {"instrumentID": 22, "positionID": 3, "isBuy": True},
        ],
    )
    assert snap.count_for_instrument(11) == 2
    assert snap.count_for_instrument(22) == 1
    assert snap.count_for_instrument(99) == 0


def test_rejection_backoff_suspends_after_threshold(engine):
    # Not suspended before threshold
    engine._register_rejection("u1", "EUR/USD", "r1")
    engine._register_rejection("u1", "EUR/USD", "r2")
    assert engine._is_symbol_suspended("u1", "EUR/USD") is None
    # Third rejection triggers suspension
    engine._register_rejection("u1", "EUR/USD", "r3")
    remaining = engine._is_symbol_suspended("u1", "EUR/USD")
    assert remaining is not None and remaining > 0
    # Clearing resumes trading
    engine._clear_rejections("u1", "EUR/USD")
    assert engine._is_symbol_suspended("u1", "EUR/USD") is None


class _Signal:
    action = SignalAction.BUY
    units = 0.1
    entry_price = 1.1000
    stop_loss = 1.0950
    take_profit = 1.1100
    order_type = "market"
    limit_price = None


def test_execute_trade_sl_tp_fail_but_real_fill_tracked(engine):
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "status": "error",
        "positionId": 555,
        "message": "Position 555 opened but failed to set stop loss: boom",
        "demo": True,
    }
    ctx = mock.Mock()
    ctx.__aenter__ = mock.AsyncMock(return_value=ctx)
    ctx.__aexit__ = mock.AsyncMock(return_value=False)
    ctx.post = mock.AsyncMock(return_value=resp)

    with mock.patch("app.bot.engine.httpx.AsyncClient") as cls:
        cls.return_value = ctx
        res = asyncio.run(
            engine._execute_trade("u1", 11, _Signal(), symbol="EUR/USD")
        )

    assert res["success"] is False
    assert res["position_id"] == 555
    assert res["rejected"] is False  # NOT an open rejection
    att = P.db.query_one(
        "SELECT * FROM position_attempts WHERE client_order_ref = ?",
        (res["client_order_ref"],),
    )
    assert att["status"] == "open"
    assert att["position_id"] == 555


def test_execute_trade_true_rejection(engine):
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "status": "error",
        "positionId": 0,
        "message": "rejected",
        "demo": True,
    }
    ctx = mock.Mock()
    ctx.__aenter__ = mock.AsyncMock(return_value=ctx)
    ctx.__aexit__ = mock.AsyncMock(return_value=False)
    ctx.post = mock.AsyncMock(return_value=resp)

    with mock.patch("app.bot.engine.httpx.AsyncClient") as cls:
        cls.return_value = ctx
        res = asyncio.run(
            engine._execute_trade("u1", 11, _Signal(), symbol="EUR/USD")
        )

    assert res["success"] is False
    assert res["position_id"] is None
    assert res["rejected"] is True
    att = P.db.query_one(
        "SELECT * FROM position_attempts WHERE client_order_ref = ?",
        (res["client_order_ref"],),
    )
    assert att["status"] == "failed"


def test_orphan_reconciliation(engine):
    import datetime

    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
    future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()

    P.create_position_attempt("u1", "orphan-open", symbol="EUR/USD", instrument_id=11, is_buy=True, units=0.1)
    P.db.execute("UPDATE position_attempts SET created_at = ? WHERE client_order_ref = ?", (past, "orphan-open"))
    P.create_position_attempt("u1", "orphan-fail", symbol="GOLD", instrument_id=99, is_buy=False, units=0.1)
    P.db.execute("UPDATE position_attempts SET created_at = ? WHERE client_order_ref = ?", (future, "orphan-fail"))

    engine._etoro_http_client.get_open_positions = mock.AsyncMock(
        return_value=[
            {
                "instrumentID": 11,
                "positionID": 777,
                "isBuy": True,
                "openRate": 1.1050,
                "openDateTime": past,
            }
        ]
    )

    asyncio.run(engine._reconcile_orphan_attempts())

    a_open = P.db.query_one("SELECT * FROM position_attempts WHERE client_order_ref = ?", ("orphan-open",))
    a_fail = P.db.query_one("SELECT * FROM position_attempts WHERE client_order_ref = ?", ("orphan-fail",))
    assert a_open["status"] == "open" and a_open["position_id"] == 777
    assert a_fail["status"] == "failed"
    ids = [p["position_id"] for p in engine.open_positions.get("u1", [])]
    assert 777 in ids