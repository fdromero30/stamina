"""Tests for atomic persistence + position lifecycle (SQLite, in-memory)."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.bot import persistence as P


@pytest.fixture(autouse=True)
def _in_memory_db():
    """Point the global persistence DB at a fresh in-memory SQLite DB."""
    old_conn = P.db._conn
    old_atomic = P.db._in_atomic
    P.db._conn = sqlite3.connect(":memory:")
    P.db._conn.row_factory = sqlite3.Row
    P.db._in_atomic = False
    P.init_db()
    yield
    try:
        P.db._conn.close()
    except Exception:
        pass
    P.db._conn = old_conn
    P.db._in_atomic = old_atomic


def test_atomic_commit():
    with P.db.atomic():
        P.create_position_attempt("u", "ref-a", symbol="EUR/USD")
        P.resolve_position_attempt("ref-a", status="open", position_id=1)
    row = P.db.query_one(
        "SELECT * FROM position_attempts WHERE client_order_ref = ?", ("ref-a",)
    )
    assert row["status"] == "open"
    assert row["position_id"] == 1


def test_atomic_rollback():
    with pytest.raises(RuntimeError):
        with P.db.atomic():
            P.create_position_attempt("u", "ref-b", symbol="EUR/USD")
            raise RuntimeError("boom")
    row = P.db.query_one(
        "SELECT * FROM position_attempts WHERE client_order_ref = ?", ("ref-b",)
    )
    assert row is None


def test_placing_attempts_queried():
    P.create_position_attempt("u", "ref-c", symbol="EUR/USD", instrument_id=10)
    placing = P.load_placing_attempts()
    assert any(a["client_order_ref"] == "ref-c" for a in placing)
    assert placing[0]["status"] == "placing"


def test_position_status_filter_and_client_ref():
    P.save_position(
        "u",
        {
            "position_id": 1,
            "entry_price": 1.1,
            "stop_loss": 1.05,
            "is_buy": True,
            "opened_at": "2026-01-01T00:00:00+00:00",
            "symbol": "EUR/USD",
            "status": "open",
            "client_order_ref": "ref-open",
        },
    )
    P.save_position(
        "u",
        {
            "position_id": 2,
            "entry_price": 1.2,
            "stop_loss": 1.15,
            "is_buy": False,
            "opened_at": "2026-01-01T00:00:00+00:00",
            "symbol": "EUR/USD",
            "status": "open",
        },
    )
    P.mark_position_closed("u", 2, reason="closed_in_etoro")
    loaded = P.load_open_positions()
    ids = [p["position_id"] for p in loaded.get("u", [])]
    assert 1 in ids
    assert 2 not in ids
    assert loaded["u"][0]["client_order_ref"] == "ref-open"