"""SQLite storage for Meeple Market, a synthetic board game shop.

Carts and orders are per-user, and every query that touches them is filtered by
`user_id` in SQL rather than filtered after the fact. That is the difference
between an ownership check and a suggestion.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_NAME = "meeple_market.db"

ORDER_STATUSES = ("placed", "packing", "shipped", "delivered", "cancelled")


def db_path() -> Path:
    env = os.environ.get("SHOP_DB_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / DEFAULT_DB_NAME


def get_conn(path: str | Path | None = None) -> sqlite3.Connection:
    target = Path(path) if path is not None else db_path()
    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    publisher   TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    stock       INTEGER NOT NULL CHECK (stock >= 0),
    players     TEXT NOT NULL,
    play_minutes INTEGER NOT NULL,
    weight      REAL NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cart_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL REFERENCES users(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    added_at   TEXT NOT NULL,
    UNIQUE (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    status      TEXT NOT NULL CHECK (
                    status IN ('placed','packing','shipped','delivered','cancelled')),
    total_cents INTEGER NOT NULL,
    placed_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id         TEXT NOT NULL REFERENCES orders(id),
    product_id       TEXT NOT NULL REFERENCES products(id),
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cart_user   ON cart_items(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_prod_cat    ON products(category);
"""


def money(cents: int) -> str:
    """Format cents as a display price. Money is stored as integers so that
    totals never drift the way floats do."""
    return f"${cents / 100:,.2f}"
