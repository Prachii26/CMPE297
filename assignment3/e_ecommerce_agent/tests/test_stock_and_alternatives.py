"""Out-of-stock items must always come back with alternatives. That is our
headline change from the reference agent."""

from __future__ import annotations

import pytest

ANA = "u_ana"

# Seeded with stock 0.
OUT_OF_STOCK = ["BG-002", "BG-006", "BG-010", "BG-014", "BG-019", "BG-023"]


@pytest.mark.parametrize("pid", OUT_OF_STOCK)
def test_get_product_on_an_out_of_stock_item_offers_alternatives(shop, pid):
    r = shop["get_product"](ANA, pid)
    assert r["stock"] == 0
    assert r["in_stock"] is False
    assert r["note"] == "out of stock - see alternatives"

    alts = r["alternatives"]
    assert 1 <= len(alts) <= 3
    for a in alts:
        assert a["stock"] > 0, "an alternative must actually be in stock"
        assert a["id"] != pid
        assert a["price"].startswith("$")
        assert a["price_difference"]
        assert a["why"]


def test_alternatives_prefer_the_same_category_and_nearest_price(shop):
    target = shop["get_product"](ANA, "BG-002")  # strategy, $62.99
    alts = target["alternatives"]
    assert all(a["category"] == "strategy" for a in alts)

    # Closest in price comes first: BG-003 at $58.99 beats BG-004 at $47.99.
    assert alts[0]["id"] == "BG-003"
    assert [a["id"] for a in alts] == ["BG-003", "BG-001", "BG-004"]


def test_add_to_cart_refuses_out_of_stock_but_still_helps(shop):
    r = shop["add_to_cart"](ANA, "BG-002", 1)
    assert r["ok"] is False
    assert r["reason"] == "out_of_stock"
    assert "out of stock" in r["message"]
    assert len(r["alternatives"]) >= 1
    # Nothing was added.
    assert shop["place_order"](ANA)["reason"] == "empty_cart"


def test_add_to_cart_refuses_more_than_stock_and_reports_what_is_left(shop):
    # BG-016 is seeded with stock 1.
    r = shop["add_to_cart"](ANA, "BG-016", 5)
    assert r["ok"] is False
    assert r["reason"] == "insufficient_stock"
    assert r["available"] == 1
    assert len(r["alternatives"]) >= 1


def test_cart_quantity_accumulates_and_is_rechecked_against_stock(shop):
    # BG-004 has stock 2.
    assert shop["add_to_cart"](ANA, "BG-004", 2)["ok"] is True
    # A second add pushes the cart total over stock, even though 1 <= 2.
    again = shop["add_to_cart"](ANA, "BG-004", 1)
    assert again["ok"] is False
    assert again["reason"] == "insufficient_stock"
    assert "already have 2" in again["message"]


def test_search_marks_out_of_stock_rows_and_attaches_alternatives(shop):
    r = shop["search_products"](ANA, category="party")
    assert r["match_count"] > 0
    assert "BG-010" in r["out_of_stock_ids"]

    oos = [p for p in r["products"] if not p["in_stock"]]
    assert oos, "expected at least one out-of-stock party game"
    for p in oos:
        assert p["alternatives"]
        assert all(a["stock"] > 0 for a in p["alternatives"])

    # In-stock items sort first and carry no alternatives.
    assert r["products"][0]["in_stock"] is True
    assert "alternatives" not in r["products"][0]


def test_search_can_hide_out_of_stock_entirely(shop):
    r = shop["search_products"](ANA, category="party", include_out_of_stock=False)
    assert r["out_of_stock_ids"] == []
    assert all(p["in_stock"] for p in r["products"])


def test_search_filters_combine(shop):
    cheap = shop["search_products"](ANA, category="travel", max_price=15.0)
    assert cheap["match_count"] >= 1
    assert all(float(p["price"].strip("$").replace(",", "")) <= 15.0
               for p in cheap["products"])

    six_player = shop["search_products"](ANA, players=6)
    for p in six_player["products"]:
        lo, _, hi = p["players"].partition("-")
        assert int(lo) <= 6 <= int(hi or lo)

    text = shop["search_products"](ANA, query="vineyard")
    assert text["match_count"] == 1
    assert text["products"][0]["id"] == "BG-002"


def test_place_order_decrements_stock_and_can_sell_out_an_item(shop):
    before = shop["get_product"](ANA, "BG-016")["stock"]
    assert before == 1

    shop["add_to_cart"](ANA, "BG-016", 1)
    order = shop["place_order"](ANA)
    assert order["ok"] is True

    after = shop["get_product"](ANA, "BG-016")
    assert after["stock"] == 0
    # And now it offers alternatives, like any other sold-out product.
    assert after["alternatives"]


def test_place_order_rechecks_stock_at_order_time(shop):
    """Ana and Ben both cart the last copy; the second order must fail cleanly
    with alternatives rather than driving stock negative."""
    shop["add_to_cart"]("u_ana", "BG-016", 1)
    shop["add_to_cart"]("u_ben", "BG-016", 1)

    first = shop["place_order"]("u_ana")
    assert first["ok"] is True

    second = shop["place_order"]("u_ben")
    assert second["ok"] is False
    assert second["reason"] == "insufficient_stock"
    problem = second["problems"][0]
    assert problem["id"] == "BG-016"
    assert problem["wanted"] == 1
    assert problem["available"] == 0
    assert problem["alternatives"]

    # Stock never went negative.
    assert shop["get_product"]("u_ben", "BG-016")["stock"] == 0


def test_quantity_bounds_and_unknown_products_are_rejected(shop):
    assert "error" in shop["add_to_cart"](ANA, "BG-001", 0)
    assert "error" in shop["add_to_cart"](ANA, "BG-001", -1)
    assert "error" in shop["add_to_cart"](ANA, "BG-001", 999)
    assert "error" in shop["add_to_cart"](ANA, "NOPE-1", 1)
    assert "error" in shop["get_product"](ANA, "NOPE-1")


def test_totals_are_computed_from_integer_cents(shop):
    shop["add_to_cart"](ANA, "BG-001", 2)   # $54.99 x2
    r = shop["add_to_cart"](ANA, "BG-021", 3)  # $9.99 x3
    assert r["cart_total"] == "$139.95"
    assert r["cart_item_count"] == 5
