"""SQLite persistence for trading bot state, cycle history, and open positions."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bot_state.db"


def _get_conn() -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cycle_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                status TEXT NOT NULL,
                evaluations TEXT NOT NULL,
                trades TEXT NOT NULL,
                adjustments TEXT NOT NULL,
                skipped INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                reason TEXT
            );

            CREATE TABLE IF NOT EXISTS open_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                position_id INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                is_buy INTEGER NOT NULL,
                breakeven_applied INTEGER NOT NULL DEFAULT 0,
                opened_at TEXT NOT NULL,
                UNIQUE(user_id, position_id)
            );
        """)

        # Migration: add `reason` column to existing cycle_history tables
        try:
            conn.execute("ALTER TABLE cycle_history ADD COLUMN reason TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

    logger.info("Bot state database initialized at %s", DB_PATH)


# ── Bot State ───────────────────────────────────────────────────────────


def save_bot_state(key: str, value: Any) -> None:
    """Save a key-value pair to the bot state table."""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO bot_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(value), datetime.now(timezone.utc).isoformat()),
        )


def load_bot_state(key: str, default: Any = None) -> Any:
    """Load a key-value pair from the bot state table."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM bot_state WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return default


# ── Cycle History ───────────────────────────────────────────────────────


def save_cycle(cycle: dict[str, Any]) -> None:
    """Persist a single cycle entry to the database."""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cycle_history (
                timestamp, source, duration_ms, status,
                evaluations, trades, adjustments, skipped, error, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cycle.get("timestamp", datetime.now(timezone.utc).isoformat()),
                cycle.get("source", "auto"),
                cycle.get("duration_ms", 0),
                cycle.get("status", "success"),
                json.dumps(cycle.get("evaluations", [])),
                json.dumps(cycle.get("trades", [])),
                json.dumps(cycle.get("adjustments", [])),
                1 if cycle.get("skipped", False) else 0,
                cycle.get("error"),
                cycle.get("reason"),
            ),
        )


def load_cycle_history(limit: int = 20) -> list[dict[str, Any]]:
    """Load recent cycle history from the database (most recent first)."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM cycle_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    cycles: list[dict[str, Any]] = []
    for row in rows:
        cycles.append({
            "timestamp": row["timestamp"],
            "source": row["source"],
            "duration_ms": row["duration_ms"],
            "status": row["status"],
            "evaluations": json.loads(row["evaluations"] or "[]"),
            "trades": json.loads(row["trades"] or "[]"),
            "adjustments": json.loads(row["adjustments"] or "[]"),
            "skipped": bool(row["skipped"]),
            "error": row["error"],
            "reason": row["reason"],
        })
    return cycles


# ── Open Positions ──────────────────────────────────────────────────────


def save_position(user_id: str, position: dict[str, Any]) -> None:
    """Persist an open position to the database."""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO open_positions (
                user_id, position_id, entry_price, stop_loss, take_profit,
                is_buy, breakeven_applied, opened_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, position_id) DO UPDATE SET
                entry_price = excluded.entry_price,
                stop_loss = excluded.stop_loss,
                take_profit = excluded.take_profit,
                is_buy = excluded.is_buy,
                breakeven_applied = excluded.breakeven_applied,
                opened_at = excluded.opened_at
            """,
            (
                user_id,
                position.get("position_id"),
                position.get("entry_price", 0),
                position.get("stop_loss"),
                position.get("take_profit"),
                1 if position.get("is_buy", False) else 0,
                1 if position.get("breakeven_applied", False) else 0,
                position.get("opened_at", datetime.now(timezone.utc).isoformat()),
            ),
        )


def update_position_breakeven(user_id: str, position_id: int, stop_loss: float) -> None:
    """Update a position's stop loss and mark breakeven as applied."""
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE open_positions
            SET stop_loss = ?, breakeven_applied = 1
            WHERE user_id = ? AND position_id = ?
            """,
            (stop_loss, user_id, position_id),
        )


def load_open_positions() -> dict[str, list[dict[str, Any]]]:
    """Load all open positions from the database, grouped by user."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM open_positions ORDER BY opened_at DESC"
        ).fetchall()

    positions: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        user_id = row["user_id"]
        if user_id not in positions:
            positions[user_id] = []
        positions[user_id].append({
            "position_id": row["position_id"],
            "entry_price": row["entry_price"],
            "stop_loss": row["stop_loss"],
            "take_profit": row["take_profit"],
            "is_buy": bool(row["is_buy"]),
            "breakeven_applied": bool(row["breakeven_applied"]),
            "opened_at": row["opened_at"],
        })
    return positions


def clear_positions() -> None:
    """Clear all open positions (e.g., on bot stop)."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM open_positions")
