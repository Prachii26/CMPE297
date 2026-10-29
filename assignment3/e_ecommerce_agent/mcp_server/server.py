"""FastMCP server for Meeple Market, served over stdio.

Five tools: search_products, get_product, add_to_cart, place_order, order_status.

Two things worth knowing before reading the code:

1. **Every tool takes `user_id` and every cart/order query filters on it in
   SQL.** There is no "fetch then check" path, because that is the one that
   eventually leaks. `order_status` for someone else's order returns the same
   not-found shape as an order that does not exist, so the tool is not an
   oracle for which order IDs are real.

2. **Out of stock is never a dead end.** Anything that cannot be supplied comes
   back with `alternatives`: in-stock products from the same category, ranked
   by how close they are in price, so the agent always has something to offer.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP

from .db import get_conn, money
from .seed import seed

mcp = FastMCP("meeple-market")

MAX_ALTERNATIVES = 3
MAX_QUANTITY = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = get_conn()
    seed(conn)
    return conn


def _user_exists(conn: sqlite3.Connection, user_id: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
        is not None
    )


def _require_user(conn: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    """Return an error dict if the user is missing or blank, else None."""
    uid = (user_id or "").strip()
    if not uid:
        return {"error": "user_id is required for every operation"}
    if not _user_exists(conn, uid):
        return {"error": f"unknown user_id {uid!r}"}
    return None


def _product_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["price"] = money(d["price_cents"])
    d["in_stock"] = d["stock"] > 0
    return d


def _alternatives(
    conn: sqlite3.Connection, product: sqlite3.Row, limit: int = MAX_ALTERNATIVES
) -> list[dict[str, Any]]:
    """In-stock products in the same category, closest in price first.

    Falls back to any in-stock product if the category has nothing left, so the
    shopper is never handed an empty list.
    """
    rows = conn.execute(
        "SELECT * FROM products WHERE category = ? AND stock > 0 AND id != ?",
        (product["category"], product["id"]),
    ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT * FROM products WHERE stock > 0 AND id != ? LIMIT 20",
            (product["id"],),
        ).fetchall()

    ranked = sorted(rows, key=lambda r: abs(r["price_cents"] - product["price_cents"]))
    out = []
    for r in ranked[:limit]:
        delta = r["price_cents"] - product["price_cents"]
        out.append({
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "price": money(r["price_cents"]),
            "stock": r["stock"],
            "price_difference": ("same price" if delta == 0
                                 else f"{money(abs(delta))} {'more' if delta > 0 else 'less'}"),
            "why": f"same category ({r['category']}), in stock",
        })
    return out


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


@mcp.tool
def search_products(
    user_id: str,
    query: str = "",
    category: str = "",
    max_price: float = 0.0,
    players: int = 0,
    include_out_of_stock: bool = True,
) -> dict[str, Any]:
    """Search the Meeple Market board game catalogue.

    Args:
        user_id: The shopper's id. Required.
        query: Free text matched against name, publisher and description.
        category: One of strategy, family, party, thematic, travel, accessory.
        max_price: Maximum price in dollars, e.g. 45.0. 0 means no limit.
        players: Only return games that support this player count. 0 means any.
        include_out_of_stock: Keep out-of-stock matches in the results, each
            with suggested alternatives. Default True.

    Returns:
        Matching products. Every out-of-stock match carries an `alternatives`
        list of in-stock products in the same category.
    """
    conn = _connect()
    try:
        if (err := _require_user(conn, user_id)):
            return err

        sql = "SELECT * FROM products WHERE 1=1"
        params: list[Any] = []
        if query.strip():
            like = f"%{query.strip()}%"
            sql += " AND (name LIKE ? OR description LIKE ? OR publisher LIKE ?)"
            params += [like, like, like]
        if category.strip():
            sql += " AND category = ?"
            params.append(category.strip().lower())
        if max_price and max_price > 0:
            sql += " AND price_cents <= ?"
            params.append(int(round(max_price * 100)))

        rows = conn.execute(sql, params).fetchall()

        if players and players > 0:
            kept = []
            for r in rows:
                spec = r["players"]
                if spec == "n/a":
                    continue
                lo, _, hi = spec.partition("-")
                try:
                    lo_i = int(lo)
                    hi_i = int(hi) if hi else lo_i
                except ValueError:
                    continue
                if lo_i <= players <= hi_i:
                    kept.append(r)
            rows = kept

        results = []
        for r in rows:
            if r["stock"] == 0 and not include_out_of_stock:
                continue
            item = _product_row(r)
            if r["stock"] == 0:
                item["alternatives"] = _alternatives(conn, r)
                item["note"] = "out of stock - see alternatives"
            results.append(item)

        results.sort(key=lambda d: (not d["in_stock"], d["name"]))
        out_of_stock = [r["id"] for r in results if not r["in_stock"]]

        return {
            "user_id": user_id,
            "match_count": len(results),
            "in_stock_count": len(results) - len(out_of_stock),
            "out_of_stock_ids": out_of_stock,
            "products": [
                {k: v for k, v in p.items() if k != "price_cents"} for p in results
            ],
        }
    finally:
        conn.close()


@mcp.tool
def get_product(user_id: str, product_id: str) -> dict[str, Any]:
    """Fetch one product in full.

    Args:
        user_id: The shopper's id. Required.
        product_id: The catalogue id, e.g. BG-001.

    Returns:
        The product, plus `alternatives` if it is out of stock.
    """
    conn = _connect()
    try:
        if (err := _require_user(conn, user_id)):
            return err
        pid = (product_id or "").strip().upper()
        row = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if row is None:
            return {"error": f"no product with id {pid!r}"}

        item = _product_row(row)
        item.pop("price_cents", None)
        if row["stock"] == 0:
            item["alternatives"] = _alternatives(conn, row)
            item["note"] = "out of stock - see alternatives"
        return item
    finally:
        conn.close()


@mcp.tool
def add_to_cart(user_id: str, product_id: str, quantity: int = 1) -> dict[str, Any]:
    """Add a product to this user's cart.

    Refuses if stock is insufficient, and returns alternatives rather than a
    bare failure.

    Args:
        user_id: The shopper's id. The cart belongs to this user alone.
        product_id: The catalogue id, e.g. BG-001.
        quantity: How many, 1 to 10.

    Returns:
        The updated cart contents and total, or an error plus `alternatives`.
    """
    conn = _connect()
    try:
        if (err := _require_user(conn, user_id)):
            return err
        pid = (product_id or "").strip().upper()
        try:
            qty = int(quantity)
        except (TypeError, ValueError):
            return {"error": f"quantity must be a whole number, got {quantity!r}"}
        if qty < 1 or qty > MAX_QUANTITY:
            return {"error": f"quantity must be between 1 and {MAX_QUANTITY}"}

        row = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if row is None:
            return {"error": f"no product with id {pid!r}"}

        already = conn.execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, pid),
        ).fetchone()
        wanted = qty + (already["quantity"] if already else 0)

        if row["stock"] == 0:
            return {
                "ok": False,
                "reason": "out_of_stock",
                "message": f"{row['name']} is out of stock.",
                "product": {"id": row["id"], "name": row["name"]},
                "alternatives": _alternatives(conn, row),
            }
        if wanted > row["stock"]:
            return {
                "ok": False,
                "reason": "insufficient_stock",
                "message": (
                    f"Only {row['stock']} of {row['name']} left"
                    + (f", and you already have {already['quantity']} in your cart."
                       if already else ".")
                ),
                "available": row["stock"],
                "product": {"id": row["id"], "name": row["name"]},
                "alternatives": _alternatives(conn, row),
            }

        conn.execute(
            "INSERT INTO cart_items (user_id, product_id, quantity, added_at)"
            " VALUES (?,?,?,?)"
            " ON CONFLICT(user_id, product_id)"
            " DO UPDATE SET quantity = quantity + excluded.quantity",
            (user_id, pid, qty, _now()),
        )
        conn.commit()
        return {"ok": True, "added": {"id": pid, "name": row["name"], "quantity": qty},
                **_cart_summary(conn, user_id)}
    finally:
        conn.close()


def _cart_summary(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT c.product_id, c.quantity, p.name, p.price_cents, p.stock"
        " FROM cart_items c JOIN products p ON p.id = c.product_id"
        " WHERE c.user_id = ? ORDER BY c.id",
        (user_id,),
    ).fetchall()
    total = sum(r["quantity"] * r["price_cents"] for r in rows)
    return {
        "cart": [
            {
                "id": r["product_id"],
                "name": r["name"],
                "quantity": r["quantity"],
                "line_total": money(r["quantity"] * r["price_cents"]),
            }
            for r in rows
        ],
        "cart_item_count": sum(r["quantity"] for r in rows),
        "cart_total": money(total),
    }


@mcp.tool
def place_order(user_id: str) -> dict[str, Any]:
    """Turn this user's cart into an order and decrement stock.

    Re-checks stock at the moment of ordering, because something may have sold
    out since it went into the cart.

    Args:
        user_id: The shopper's id. Only this user's cart is ordered.

    Returns:
        The new order id, its total and status, or an error naming the lines
        that could not be supplied, each with alternatives.
    """
    conn = _connect()
    try:
        if (err := _require_user(conn, user_id)):
            return err

        rows = conn.execute(
            "SELECT c.product_id, c.quantity, p.name, p.price_cents, p.stock,"
            " p.category FROM cart_items c JOIN products p ON p.id = c.product_id"
            " WHERE c.user_id = ? ORDER BY c.id",
            (user_id,),
        ).fetchall()
        if not rows:
            return {"ok": False, "reason": "empty_cart",
                    "message": "Your cart is empty."}

        problems = []
        for r in rows:
            if r["quantity"] > r["stock"]:
                product = conn.execute(
                    "SELECT * FROM products WHERE id = ?", (r["product_id"],)
                ).fetchone()
                problems.append({
                    "id": r["product_id"],
                    "name": r["name"],
                    "wanted": r["quantity"],
                    "available": r["stock"],
                    "alternatives": _alternatives(conn, product),
                })
        if problems:
            return {
                "ok": False,
                "reason": "insufficient_stock",
                "message": "Some items in your cart are no longer available.",
                "problems": problems,
            }

        total = sum(r["quantity"] * r["price_cents"] for r in rows)
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        conn.execute(
            "INSERT INTO orders (id,user_id,status,total_cents,placed_at)"
            " VALUES (?,?,?,?,?)",
            (order_id, user_id, "placed", total, _now()),
        )
        conn.executemany(
            "INSERT INTO order_items (order_id,product_id,quantity,unit_price_cents)"
            " VALUES (?,?,?,?)",
            [(order_id, r["product_id"], r["quantity"], r["price_cents"]) for r in rows],
        )
        for r in rows:
            conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (r["quantity"], r["product_id"]),
            )
        conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        conn.commit()

        return {
            "ok": True,
            "order_id": order_id,
            "status": "placed",
            "total": money(total),
            "line_count": len(rows),
            "items": [
                {"id": r["product_id"], "name": r["name"], "quantity": r["quantity"]}
                for r in rows
            ],
        }
    finally:
        conn.close()


@mcp.tool
def order_status(user_id: str, order_id: str = "") -> dict[str, Any]:
    """Look up this user's orders, or one specific order they own.

    A user can only ever see their own orders. Asking for someone else's order
    returns the same "not found" answer as an order that does not exist, so
    this tool cannot be used to discover which order ids are real.

    Args:
        user_id: The shopper's id.
        order_id: A specific order, e.g. ORD-1001. Empty lists all their orders.

    Returns:
        The order with its line items, or the user's order list.
    """
    conn = _connect()
    try:
        if (err := _require_user(conn, user_id)):
            return err

        oid = (order_id or "").strip().upper()
        if not oid:
            rows = conn.execute(
                "SELECT id, status, total_cents, placed_at FROM orders"
                " WHERE user_id = ? ORDER BY placed_at DESC",
                (user_id,),
            ).fetchall()
            return {
                "user_id": user_id,
                "order_count": len(rows),
                "orders": [
                    {
                        "order_id": r["id"],
                        "status": r["status"],
                        "total": money(r["total_cents"]),
                        "placed_at": r["placed_at"],
                    }
                    for r in rows
                ],
            }

        # Ownership is enforced in the WHERE clause, not after the fetch.
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ? AND user_id = ?", (oid, user_id)
        ).fetchone()
        if row is None:
            return {"error": f"no order {oid!r} for this user"}

        items = conn.execute(
            "SELECT oi.product_id, oi.quantity, oi.unit_price_cents, p.name"
            " FROM order_items oi JOIN products p ON p.id = oi.product_id"
            " WHERE oi.order_id = ?",
            (oid,),
        ).fetchall()
        return {
            "order_id": row["id"],
            "status": row["status"],
            "total": money(row["total_cents"]),
            "placed_at": row["placed_at"],
            "items": [
                {
                    "id": i["product_id"],
                    "name": i["name"],
                    "quantity": i["quantity"],
                    "unit_price": money(i["unit_price_cents"]),
                }
                for i in items
            ],
        }
    finally:
        conn.close()


def main() -> None:
    conn = _connect()
    conn.close()
    mcp.run()


if __name__ == "__main__":
    main()
