"""Synthetic catalogue and users for Meeple Market.

Several products are deliberately seeded with stock 0, because the
out-of-stock-returns-alternatives path is the behaviour we most want to
demonstrate and test.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from .db import SCHEMA

USERS = [
    ("u_ana", "Ana Ruiz"),
    ("u_ben", "Ben Okafor"),
    ("u_chi", "Chiara Rossi"),
]

# (id, name, category, publisher, price_cents, stock, players, minutes, weight, desc)
PRODUCTS = [
    ("BG-001", "Harbour Routes", "strategy", "Northwind Games", 5499, 7,
     "2-4", 90, 3.2, "Build shipping lanes between rival ports. Heavy on route planning, light on luck."),
    ("BG-002", "Terra Vineyards", "strategy", "Vermillion", 6299, 0,
     "1-4", 110, 3.6, "Worker placement set on a growing vineyard estate. Solo mode included."),
    ("BG-003", "Clockwork Spires", "strategy", "Northwind Games", 5899, 4,
     "2-4", 100, 3.4, "Engine builder where every gear you place speeds up the next turn."),
    ("BG-004", "Saltmarsh", "strategy", "Tidewater", 4799, 2,
     "1-4", 75, 2.9, "Tile-laying reclamation game. Flood the wrong polder and lose a season."),
    ("BG-005", "Paper Lanterns", "family", "Lanternlight", 3299, 12,
     "2-5", 40, 1.8, "Gentle set collection with beautiful artwork. A good gateway game."),
    ("BG-006", "Night Market", "family", "Lanternlight", 2999, 0,
     "2-5", 35, 1.6, "Press-your-luck haggling in a bustling street market."),
    ("BG-007", "Cloud Kitchen", "family", "Vermillion", 3499, 9,
     "2-4", 45, 1.9, "Cooperative order-filling under a ticking clock. Cheerful and quick."),
    ("BG-008", "Badger & Bramble", "family", "Tidewater", 2799, 15,
     "2-4", 30, 1.4, "Woodland race game. Simple rules, lots of table talk."),
    ("BG-009", "Signal Lost", "party", "Megaphone", 2499, 20,
     "4-8", 25, 1.2, "Hidden-role deduction aboard a failing space station."),
    ("BG-010", "Charades Deluxe", "party", "Megaphone", 1999, 0,
     "4-12", 30, 1.0, "Three hundred prompts and a very loud timer."),
    ("BG-011", "Word Hoard", "party", "Lanternlight", 2299, 11,
     "3-8", 30, 1.1, "Competitive word building with a press-your-luck scoring twist."),
    ("BG-012", "Rooftop Chase", "party", "Megaphone", 2699, 6,
     "3-6", 20, 1.3, "Real-time card slapping across a neon skyline."),
    ("BG-013", "The Long Winter", "thematic", "Vermillion", 7499, 3,
     "1-4", 150, 4.1, "Survival campaign across twelve linked scenarios. Legacy elements."),
    ("BG-014", "Deepwater Salvage", "thematic", "Tidewater", 6899, 0,
     "2-4", 120, 3.8, "Dive a wreck, manage air, decide when greed becomes fatal."),
    ("BG-015", "Hollow Crown", "thematic", "Northwind Games", 7199, 5,
     "3-6", 180, 4.3, "Area control and betrayal in a collapsing kingdom."),
    ("BG-016", "Ash & Ember", "thematic", "Vermillion", 6599, 1,
     "2", 60, 3.0, "Two-player duel of fire mages with asymmetric decks."),
    ("BG-017", "Pocket Caravan", "travel", "Lanternlight", 1499, 25,
     "1-2", 20, 1.5, "A whole trading game in a tin. Travel friendly."),
    ("BG-018", "Index Card Dungeon", "travel", "Megaphone", 1299, 18,
     "1", 15, 1.7, "Solo roll-and-write crawl. Pencil not included."),
    ("BG-019", "Sky Ferry", "travel", "Tidewater", 1699, 0,
     "2-4", 25, 1.6, "Compact pick-up-and-deliver with magnetic pieces."),
    ("BG-020", "Tide Pools", "travel", "Northwind Games", 1899, 14,
     "1-4", 25, 1.8, "Tiny tile game about rock pools filling and emptying."),
    ("BG-021", "Sleeve Pack 100", "accessory", "Northwind Games", 999, 60,
     "n/a", 0, 1.0, "Standard card sleeves, 100 count, matte finish."),
    ("BG-022", "Meeple Set, Wood", "accessory", "Lanternlight", 1499, 30,
     "n/a", 0, 1.0, "Sixty wooden meeples in six colours."),
    ("BG-023", "Dice Tower, Walnut", "accessory", "Vermillion", 3999, 0,
     "n/a", 0, 1.0, "Flat-pack walnut dice tower with felt landing tray."),
    ("BG-024", "Game Mat, 36in", "accessory", "Tidewater", 2999, 8,
     "n/a", 0, 1.0, "Neoprene playmat, rolls flat, machine washable."),
]


def seed(conn: sqlite3.Connection, force: bool = False) -> int:
    """Create the schema and load the fixture data. Returns products inserted."""
    conn.executescript(SCHEMA)
    if force:
        conn.executescript(
            "DELETE FROM order_items; DELETE FROM orders; DELETE FROM cart_items;"
            " DELETE FROM products; DELETE FROM users;"
        )
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] and not force:
        return 0

    conn.executemany("INSERT INTO users (id, display_name) VALUES (?,?)", USERS)
    conn.executemany(
        "INSERT INTO products (id,name,category,publisher,price_cents,stock,"
        "players,play_minutes,weight,description) VALUES (?,?,?,?,?,?,?,?,?,?)",
        PRODUCTS,
    )

    # One historical order each for Ana and Ben, so order_status and the
    # ownership checks have something real to work against.
    now = datetime.now(timezone.utc)
    history = [
        ("ORD-1001", "u_ana", "shipped", 3, [("BG-005", 1, 3299), ("BG-021", 2, 999)]),
        ("ORD-1002", "u_ben", "delivered", 11, [("BG-009", 1, 2499)]),
        ("ORD-1003", "u_ana", "packing", 1, [("BG-017", 1, 1499)]),
    ]
    for order_id, user_id, status, days_ago, items in history:
        total = sum(q * p for _, q, p in items)
        conn.execute(
            "INSERT INTO orders (id,user_id,status,total_cents,placed_at)"
            " VALUES (?,?,?,?,?)",
            (
                order_id,
                user_id,
                status,
                total,
                (now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
            ),
        )
        conn.executemany(
            "INSERT INTO order_items (order_id,product_id,quantity,unit_price_cents)"
            " VALUES (?,?,?,?)",
            [(order_id, pid, qty, price) for pid, qty, price in items],
        )

    conn.commit()
    return len(PRODUCTS)
