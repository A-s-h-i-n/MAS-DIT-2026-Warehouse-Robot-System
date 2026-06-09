"""SQLite persistence layer.

The simulation keeps its authoritative state in memory (so the tick loop is
fast and consistent). This module mirrors that state into SQLite using the
schema defined in the project spec, so the warehouse is inspectable and the
data survives restarts of read-only history.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("wms.db")

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS robots (
    id INTEGER PRIMARY KEY,
    name TEXT,
    battery INTEGER,
    status TEXT,
    x INTEGER,
    y INTEGER,
    current_task TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    item TEXT,
    quantity INTEGER,
    priority TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    robot_id INTEGER,
    order_id INTEGER,
    status TEXT,
    start_time TEXT,
    end_time TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY,
    item TEXT,
    stock INTEGER,
    location_x INTEGER,
    location_y INTEGER
);
"""


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        logger.info("Connected to SQLite at %s", settings.DB_PATH)
    return _conn


def init_db() -> None:
    conn = connect()
    with _lock:
        conn.executescript(SCHEMA)
        conn.commit()


def upsert_robot(rid: int, name: str, battery: int, status: str,
                 x: int, y: int, current_task: str | None) -> None:
    conn = connect()
    with _lock:
        conn.execute(
            """INSERT INTO robots (id, name, battery, status, x, y, current_task)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, battery=excluded.battery, status=excluded.status,
                 x=excluded.x, y=excluded.y, current_task=excluded.current_task""",
            (rid, name, battery, status, x, y, current_task),
        )
        conn.commit()


def upsert_order(oid: int, item: str, quantity: int, priority: str, status: str) -> None:
    conn = connect()
    with _lock:
        conn.execute(
            """INSERT INTO orders (id, item, quantity, priority, status)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 item=excluded.item, quantity=excluded.quantity,
                 priority=excluded.priority, status=excluded.status""",
            (oid, item, quantity, priority, status),
        )
        conn.commit()


def upsert_task(tid: int, robot_id: int | None, order_id: int, status: str,
                start_time: str | None, end_time: str | None) -> None:
    conn = connect()
    with _lock:
        conn.execute(
            """INSERT INTO tasks (id, robot_id, order_id, status, start_time, end_time)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 robot_id=excluded.robot_id, order_id=excluded.order_id,
                 status=excluded.status, start_time=excluded.start_time,
                 end_time=excluded.end_time""",
            (tid, robot_id, order_id, status, start_time, end_time),
        )
        conn.commit()


def upsert_inventory(iid: int, item: str, stock: int, x: int, y: int) -> None:
    conn = connect()
    with _lock:
        conn.execute(
            """INSERT INTO inventory (id, item, stock, location_x, location_y)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 item=excluded.item, stock=excluded.stock,
                 location_x=excluded.location_x, location_y=excluded.location_y""",
            (iid, item, stock, x, y),
        )
        conn.commit()


def reset() -> None:
    """Wipe all tables — used when the simulation world is reset."""
    conn = connect()
    with _lock:
        for table in ("robots", "orders", "tasks", "inventory"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
