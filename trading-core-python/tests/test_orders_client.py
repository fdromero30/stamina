"""Tests for unified eToro client (demo as request param, not URL suffix)."""
import asyncio
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.integrations.orders_client import EtoroHttpClient
from app.settings import settings


def _run(coro):
    return asyncio.run(coro)


def _ctx(method):
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"ok": True}
    ctx = mock.Mock()
    ctx.__aenter__ = mock.AsyncMock(return_value=ctx)
    ctx.__aexit__ = mock.AsyncMock(return_value=False)
    setattr(ctx, method, mock.AsyncMock(return_value=resp))
    return ctx


def _patch_http(coro, method):
    ctx = _ctx(method)
    with mock.patch("app.integrations.orders_client.httpx.AsyncClient") as cls:
        cls.return_value = ctx
        _run(coro)
    return getattr(ctx, method).call_args


def test_open_by_units_demo_es_parametro_no_sufijo():
    call = _patch_http(
        EtoroHttpClient("http://backend").open_by_units("u1", 100000, True, 10.0, demo=True),
        "post",
    )
    assert call.args[0] == "http://backend/etoro/trading/open-by-units"
    assert "/demo/" not in call.args[0]
    assert call.kwargs["params"]["demo"] == "true"


def test_open_by_units_sin_demo_usa_settings():
    original = settings.use_demo_account
    settings.use_demo_account = False
    try:
        call = _patch_http(
            EtoroHttpClient("http://backend").open_by_units("u1", 100000, True, 10.0),
            "post",
        )
        assert call.args[0] == "http://backend/etoro/trading/open-by-units"
        assert call.kwargs["params"]["demo"] == "false"
    finally:
        settings.use_demo_account = original


def test_update_stop_loss_envia_demo_param():
    call = _patch_http(
        EtoroHttpClient("http://backend").update_stop_loss("u1", 55, 1.0450, demo=False),
        "put",
    )
    assert call.args[0] == "http://backend/etoro/trading/stop-loss/55"
    assert call.kwargs["params"]["demo"] == "false"


def test_get_open_positions_url_unificada():
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"positions": [{"positionID": 1}]}
    ctx = mock.Mock()
    ctx.__aenter__ = mock.AsyncMock(return_value=ctx)
    ctx.__aexit__ = mock.AsyncMock(return_value=False)
    ctx.get = mock.AsyncMock(return_value=resp)

    with mock.patch("app.integrations.orders_client.httpx.AsyncClient") as cls:
        cls.return_value = ctx
        result = _run(EtoroHttpClient("http://backend").get_open_positions("u1", demo=True))

    call = ctx.get.call_args
    assert result == [{"positionID": 1}]
    assert "/demo/" not in call.args[0]
    assert call.args[0].endswith("/etoro/portfolio/positions")
    assert call.kwargs["params"]["demo"] == "true"


def test_cancel_order_defaults_a_settings():
    original = settings.use_demo_account
    settings.use_demo_account = True
    try:
        call = _patch_http(
            EtoroHttpClient("http://backend").cancel_order("u1", 77),
            "delete",
        )
        assert call.args[0] == "http://backend/etoro/trading/cancel-order/77"
        assert call.kwargs["params"]["demo"] == "true"
    finally:
        settings.use_demo_account = original