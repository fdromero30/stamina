"""Persistence using SQLite (local) or PostgreSQL (Supabase / production).

If `settings.database_url` is set, PostgreSQL is used; otherwise local SQLite.
The schema is portable: TEXT for timestamps/JSON keeps it compatible with both.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ..settings import settings

logger = logging.getLogger(__name__)


class Database:
    """Uniform DB wrapper. Creates the connection on first use (lazy)."""

    def __init__(self, url: str = "") -> None:
        self._url = url.strip()
        self._conn: Any = None  # sqlite3.Connection | psycopg2 connection

    @property
    def engine(self) -> str:
        return "postgres" if self._url.startswith("postgres") else "sqlite"

    def _prepare_sql(self, sql: str) -> str:
        """Translate SQLite `?` placeholders to psycopg2 `%s` for PostgreSQL."""
        if self.engine == "postgres":
            return sql.replace("?", "%s")
        return sql

    def _ensure_conn(self) -> Any:
        if self._conn is not None:
            return self._conn
        if self.engine == "postgres":
            import psycopg2

            self._conn = psycopg2.connect(self._url)
            self._conn.autocommit = True
        else:
            # SQLite: stored under ./data/bot_state.db
            from pathlib import Path

            db_path = Path(__file__).resolve().parent.parent / "data" / "bot_state.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # ── Helpers for unified execute/query ───────────────────────────
    def execute(self, sql: str, params: tuple = ()) -> Any:
        conn = self._ensure_conn()
        cur = conn.cursor()
        cur.execute(self._prepare_sql(sql), params)
        self._close_cursor(cur)
        return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        conn = self._ensure_conn()
        cur = conn.cursor()
        cur.execute(self._prepare_sql(sql), params)
        if self.engine == "postgres":
            cols = [d.name for d in cur.description] if cur.description else []
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        else:
            rows = [dict(r) for r in cur.fetchall()]
        self._close_cursor(cur)
        return rows

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def _close_cursor(self, cur: Any) -> None:
        try:
            cur.close()
        except Exception:
            pass


# ── Global DB instance (choose backend from settings) ──────────────────
db = Database(url=settings.database_url)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: Optional[str], default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


# ── Schema ──────────────────────────────────────────────────────────────


def _autoinc_primary_key() -> str:
    """Return engine-specific autoincrement INTEGER PRIMARY KEY clause."""
    if db.engine == "postgres":
        return "id SERIAL PRIMARY KEY"
    return "id INTEGER PRIMARY KEY AUTOINCREMENT"


def _migrate_columns(table: str, columns: list[tuple[str, str]]) -> None:
    """
    Add columns to an existing table if they are missing.
    Portable across SQLite and PostgreSQL.

    ``columns`` is a list of (column_name, column_definition) tuples,
    e.g. [("state", "INTEGER NOT NULL DEFAULT 0"), ("sl_original", "REAL")].
    """
    # Inspect existing columns (portable approach: query against the table).
    try:
        if db.engine == "postgres":
            rows = db.query(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = ?
                """,
                (table,),
            )
            existing = {r["column_name"] for r in rows}
        else:
            # SQLite: PRAGMA table_info
            conn = db._ensure_conn()
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table})")
            rows = cur.fetchall()
            existing = {r[1] for r in rows}
            cur.close()
    except Exception as e:
        logger.warning("Failed to inspect columns for %s: %s", table, e)
        return

    for col_name, col_def in columns:
        if col_name not in existing:
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                logger.info("Migrated: added column %s.%s", table, col_name)
            except Exception as e:
                logger.warning("Failed to add column %s.%s: %s", table, col_name, e)


def init_db() -> None:
    """Create tables if they don't exist (portable schema)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS bot_runs (
            id           TEXT PRIMARY KEY,
            started_at   TEXT NOT NULL,
            stopped_at   TEXT,
            status       TEXT NOT NULL DEFAULT 'active',
            cycles_count INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS bot_cycles (
            id          TEXT PRIMARY KEY,
            run_id      TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT 'auto',
            duration_ms REAL NOT NULL,
            status      TEXT NOT NULL DEFAULT 'success',
            evaluations TEXT NOT NULL DEFAULT '[]',
            trades      TEXT NOT NULL DEFAULT '[]',
            adjustments TEXT NOT NULL DEFAULT '[]',
            skipped     INTEGER NOT NULL DEFAULT 0,
            error       TEXT,
            reason      TEXT
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_bot_cycles_run
        ON bot_cycles(run_id)
    """)
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS open_positions (
            {_autoinc_primary_key()},
            user_id TEXT NOT NULL,
            position_id INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            is_buy INTEGER NOT NULL,
            breakeven_applied INTEGER NOT NULL DEFAULT 0,
            opened_at TEXT NOT NULL,
            -- Risk state machine columns
            state INTEGER NOT NULL DEFAULT 0,
            sl_original REAL,
            tp_fixed REAL,
            highest_price REAL,
            lowest_price REAL,
            spread_real REAL,
            UNIQUE(user_id, position_id)
        )
    """)
    # Legacy: add `reason` column if missing (old cycle_history renamed)
    try:
        db.execute("ALTER TABLE bot_cycles ADD COLUMN reason TEXT")
    except Exception:
        pass

    # Risk state machine columns — migrate existing tables if missing
    _migrate_columns("open_positions", [
        ("state", "INTEGER NOT NULL DEFAULT 0"),
        ("sl_original", "REAL"),
        ("tp_fixed", "REAL"),
        ("highest_price", "REAL"),
        ("lowest_price", "REAL"),
        ("spread_real", "REAL"),
    ])
    # Backfill sl_original for existing positions at state 0 (their current SL is the original)
    try:
        db.execute(
            "UPDATE open_positions SET sl_original = stop_loss WHERE sl_original IS NULL AND state = 0"
        )
    except Exception:
        pass

    logger.info("Database initialized (engine=%s)", db.engine)


# ── Bot State ───────────────────────────────────────────────────────────


def save_bot_state(key: str, value: Any) -> None:
    db.execute(
        """
        INSERT INTO bot_state (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, _dumps(value), _now_iso()),
    )


def load_bot_state(key: str, default: Any = None) -> Any:
    row = db.query_one("SELECT value FROM bot_state WHERE key = ?", (key,))
    if row is None:
        return default
    return _loads(row["value"], default)


# ── Bot Runs (executions) ───────────────────────────────────────────────


def start_run() -> str:
    """Start a new execution record and return its UUID id."""
    run_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO bot_runs (id, started_at, stopped_at, status, cycles_count, created_at)
        VALUES (?, ?, NULL, 'active', 0, ?)
        """,
        (run_id, _now_iso(), _now_iso()),
    )
    logger.info("New bot run started: %s", run_id)
    return run_id


def finish_run(run_id: Optional[str], status: str = "stopped") -> None:
    """Stop an execution (stopped or crashed)."""
    if not run_id:
        return
    db.execute(
        "UPDATE bot_runs SET stopped_at = ?, status = ? WHERE id = ?",
        (_now_iso(), status, run_id),
    )
    logger.info("Bot run %s finished with status=%s", run_id, status)


def mark_crashed_runs() -> None:
    """Mark any 'active' runs (no stopped_at) as crashed (e.g. after restart)."""
    db.execute(
        "UPDATE bot_runs SET status = 'crashed', stopped_at = ? WHERE status = 'active' AND stopped_at IS NULL",
        (_now_iso(),),
    )


def increment_run_cycles(run_id: Optional[str]) -> None:
    if not run_id:
        return
    db.execute(
        "UPDATE bot_runs SET cycles_count = cycles_count + 1 WHERE id = ?",
        (run_id,),
    )


# ── Cycles ──────────────────────────────────────────────────────────────


def save_cycle(cycle: dict[str, Any], run_id: Optional[str] = None) -> None:
    """Persist one cycle entry, associated with the given run (if any)."""
    db.execute(
        """
        INSERT INTO bot_cycles (
            id, run_id, timestamp, source, duration_ms, status,
            evaluations, trades, adjustments, skipped, error, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            run_id,
            cycle.get("timestamp", _now_iso()),
            cycle.get("source", "auto"),
            cycle.get("duration_ms", 0),
            cycle.get("status", "success"),
            _dumps(cycle.get("evaluations", [])),
            _dumps(cycle.get("trades", [])),
            _dumps(cycle.get("adjustments", [])),
            1 if cycle.get("skipped", False) else 0,
            cycle.get("error"),
            cycle.get("reason"),
        ),
    )


def load_cycle_history(limit: int = 20) -> list[dict[str, Any]]:
    """Load recent cycles (most recent first)."""
    rows = db.query(
        """
        SELECT * FROM bot_cycles
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )
    cycles = []
    for row in rows:
        cycles.append(_row_to_cycle(row))
    return cycles


def load_cycles_by_run(run_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Load cycles belonging to a specific run (most recent first)."""
    rows = db.query(
        """
        SELECT * FROM bot_cycles
        WHERE run_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (run_id, limit),
    )
    return [_row_to_cycle(r) for r in rows]


def load_runs(limit: int = 10) -> list[dict[str, Any]]:
    """Load recent executions (most recent first)."""
    rows = db.query(
        """
        SELECT id, started_at, stopped_at, status, cycles_count
        FROM bot_runs
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in rows]


def _row_to_cycle(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "run_id": row.get("run_id"),
        "timestamp": row.get("timestamp"),
        "source": row.get("source"),
        "duration_ms": row.get("duration_ms"),
        "status": row.get("status"),
        "evaluations": _loads(row.get("evaluations"), []),
        "trades": _loads(row.get("trades"), []),
        "adjustments": _loads(row.get("adjustments"), []),
        "skipped": bool(row.get("skipped")),
        "error": row.get("error"),
        "reason": row.get("reason"),
    }


# ── Open Positions ──────────────────────────────────────────────────────


def save_position(user_id: str, position: dict[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO open_positions (
            user_id, position_id, entry_price, stop_loss, take_profit,
            is_buy, breakeven_applied, opened_at,
            state, sl_original, tp_fixed, highest_price, lowest_price, spread_real
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, position_id) DO UPDATE SET
            entry_price = excluded.entry_price,
            stop_loss = excluded.stop_loss,
            take_profit = excluded.take_profit,
            is_buy = excluded.is_buy,
            breakeven_applied = excluded.breakeven_applied,
            opened_at = excluded.opened_at,
            state = excluded.state,
            sl_original = excluded.sl_original,
            tp_fixed = excluded.tp_fixed,
            highest_price = excluded.highest_price,
            lowest_price = excluded.lowest_price,
            spread_real = excluded.spread_real
        """,
        (
            user_id,
            position.get("position_id"),
            position.get("entry_price", 0),
            position.get("stop_loss"),
            position.get("take_profit"),
            1 if position.get("is_buy", False) else 0,
            1 if position.get("breakeven_applied", False) else 0,
            position.get("opened_at", _now_iso()),
            position.get("state", 0),
            position.get("sl_original"),
            position.get("tp_fixed"),
            position.get("highest_price"),
            position.get("lowest_price"),
            position.get("spread_real"),
        ),
    )


def update_position_breakeven(user_id: str, position_id: int, stop_loss: float) -> None:
    """Legacy breakeven update — sets state to 1 and stores the new SL."""
    db.execute(
        """
        UPDATE open_positions
        SET stop_loss = ?, breakeven_applied = 1, state = 1
        WHERE user_id = ? AND position_id = ?
        """,
        (stop_loss, user_id, position_id),
    )


def update_position_state(
    user_id: str,
    position_id: int,
    *,
    state: int,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    highest_price: Optional[float] = None,
    lowest_price: Optional[float] = None,
    spread_real: Optional[float] = None,
) -> None:
    """
    Update the risk-state machine fields of an open position.
    Only updates the fields explicitly provided (non-None).
    """
    sets: list[str] = ["state = ?"]
    params: list[Any] = [state]
    if stop_loss is not None:
        sets.append("stop_loss = ?")
        params.append(stop_loss)
    if take_profit is not None:
        sets.append("take_profit = ?")
        params.append(take_profit)
    if highest_price is not None:
        sets.append("highest_price = ?")
        params.append(highest_price)
    if lowest_price is not None:
        sets.append("lowest_price = ?")
        params.append(lowest_price)
    if spread_real is not None:
        sets.append("spread_real = ?")
        params.append(spread_real)
    params.extend([user_id, position_id])

    db.execute(
        f"UPDATE open_positions SET {', '.join(sets)} WHERE user_id = ? AND position_id = ?",
        tuple(params),
    )


def delete_position(user_id: str, position_id: int) -> None:
    """Remove a tracked position/order from the persistence store."""
    db.execute(
        "DELETE FROM open_positions WHERE user_id = ? AND position_id = ?",
        (user_id, position_id),
    )


def load_open_positions() -> dict[str, list[dict[str, Any]]]:
    rows = db.query("SELECT * FROM open_positions ORDER BY opened_at DESC")
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
            "state": row.get("state", 0),
            "sl_original": row.get("sl_original"),
            "tp_fixed": row.get("tp_fixed"),
            "highest_price": row.get("highest_price"),
            "lowest_price": row.get("lowest_price"),
            "spread_real": row.get("spread_real"),
            "order_type": "market",
            "units": row.get("units", 0) if "units" in row else 0.0,
            "is_pending_order": False,
        })
    return positions


def clear_positions() -> None:
    db.execute("DELETE FROM open_positions")
