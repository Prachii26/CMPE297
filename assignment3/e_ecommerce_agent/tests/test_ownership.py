"""Ownership is the security property of this agent: a user may only ever read
and write their own cart and orders."""

from __future__ import annotations

import pytest

ANA, BEN, CHI = "u_ana", "u_ben", "u_chi"


def test_every_tool_refuses_a_missing_or_unknown_user(shop):
    for name, call in (
        ("search_products", lambda u: shop["search_products"](u, query="a")),
        ("get_product", lambda u: shop["get_product"](u, "BG-001")),
        ("add_to_cart", lambda u: shop["add_to_cart"](u, "BG-001", 1)),
        ("place_order", lambda u: shop["place_order"](u)),
        ("order_status", lambda u: shop["order_status"](u)),
    ):
        blank = call("")
        assert "error" in blank, f"{name} accepted a blank user_id"
        assert "required" in blank["error"]

        unknown = call("u_attacker")
        assert "error" in unknown, f"{name} accepted an unknown user_id"
        assert "unknown user_id" in unknown["error"]


def test_a_user_cannot_read_another_users_order(shop):
    # ORD-1001 is seeded as Ana's.
    ana_view = shop["order_status"](ANA, "ORD-1001")
    assert ana_view["order_id"] == "ORD-1001"
    assert ana_view["status"] == "shipped"

    ben_view = shop["order_status"](BEN, "ORD-1001")
    assert "error" in ben_view
    assert "order_id" not in ben_view
    assert "status" not in ben_view


def test_the_denial_does_not_leak_whether_an_order_exists(shop):
    """A different error for 'exists but not yours' vs 'does not exist' would
    turn this tool into an order-id oracle."""
    not_yours = shop["order_status"](BEN, "ORD-1001")
    never_existed = shop["order_status"](BEN, "ORD-9999")
    assert not_yours["error"].replace("ORD-1001", "X") == \
        never_existed["error"].replace("ORD-9999", "X")


def test_order_listing_is_scoped_to_the_caller(shop):
    ana = shop["order_status"](ANA)
    ben = shop["order_status"](BEN)
    chi = shop["order_status"](CHI)

    ana_ids = {o["order_id"] for o in ana["orders"]}
    ben_ids = {o["order_id"] for o in ben["orders"]}

    assert ana_ids == {"ORD-1001", "ORD-1003"}
    assert ben_ids == {"ORD-1002"}
    assert ana_ids.isdisjoint(ben_ids)
    assert chi["order_count"] == 0


def test_carts_do_not_bleed_between_users(shop):
    shop["add_to_cart"](ANA, "BG-001", 1)
    shop["add_to_cart"](BEN, "BG-005", 2)

    ana_cart = shop["add_to_cart"](ANA, "BG-021", 1)["cart"]
    ana_ids = {i["id"] for i in ana_cart}
    assert ana_ids == {"BG-001", "BG-021"}
    assert "BG-005" not in ana_ids

    ben_cart = shop["add_to_cart"](BEN, "BG-022", 1)["cart"]
    assert {i["id"] for i in ben_cart} == {"BG-005", "BG-022"}


def test_placing_an_order_only_consumes_the_callers_cart(shop):
    shop["add_to_cart"](ANA, "BG-001", 1)
    shop["add_to_cart"](BEN, "BG-005", 1)

    order = shop["place_order"](ANA)
    assert order["ok"] is True
    assert [i["id"] for i in order["items"]] == ["BG-001"]

    # Ana's cart is cleared, Ben's is untouched.
    assert shop["place_order"](ANA)["reason"] == "empty_cart"
    ben_order = shop["place_order"](BEN)
    assert ben_order["ok"] is True
    assert [i["id"] for i in ben_order["items"]] == ["BG-005"]


def test_a_new_order_is_only_visible_to_its_owner(shop):
    shop["add_to_cart"](CHI, "BG-009", 1)
    order_id = shop["place_order"](CHI)["order_id"]

    assert shop["order_status"](CHI, order_id)["order_id"] == order_id
    assert "error" in shop["order_status"](ANA, order_id)
    assert "error" in shop["order_status"](BEN, order_id)
