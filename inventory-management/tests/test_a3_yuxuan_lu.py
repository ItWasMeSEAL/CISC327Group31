"""Tests for the stock movement page and low-stock notifications."""

from unittest.mock import patch

import pytest


@pytest.fixture
def product_id(client):
    response = client.post(
        "/products",
        json={
            "name": "Work Gloves",
            "sku": "GLOVES-001",
            "unit_price": 8.50,
            "quantity_on_hand": 10,
            "reorder_level": 5,
        },
    )
    assert response.status_code == 201
    return response.get_json()["id"]


@pytest.mark.parametrize(
    ("movement", "quantity", "expected_stock"),
    [("IN", 4, 14), ("OUT", 10, 0)],
)
def test_transaction_form_records_movement_and_updates_stock(
    client, product_id, movement, quantity, expected_stock
):
    supplier_id = None
    if movement == "IN":
        supplier = client.post(
            "/suppliers",
            json={"name": "Tool Supply", "contact_email": "supply@example.com"},
        )
        assert supplier.status_code == 201
        supplier_id = supplier.get_json()["id"]

    response = client.post(
        "/ui/transactions",
        data={
            "product_id": str(product_id),
            "type": movement,
            "quantity": str(quantity),
            "supplier_id": str(supplier_id) if supplier_id is not None else "",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/ui/transactions"
    stock = client.get(f"/products/{product_id}/stock-level").get_json()
    assert stock["quantity_on_hand"] == expected_stock

    records = client.get("/transactions").get_json()
    assert len(records) == 1
    record = records[0]
    assert record["product_id"] == product_id
    assert record["supplier_id"] == supplier_id
    assert record["type"] == movement
    assert record["quantity"] == quantity

    page = client.get(response.headers["Location"])
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "<h1>Transactions</h1>" in html
    assert f"<td>{movement}</td>" in html
    assert f"<td>{quantity}</td>" in html


def test_transaction_form_for_unknown_product_leaves_inventory_unchanged(
    client, product_id
):
    before = client.get(f"/products/{product_id}").get_json()
    response = client.post(
        "/ui/transactions",
        data={"product_id": str(product_id + 1), "type": "IN", "quantity": "4"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/ui/transactions"
    assert client.get("/transactions").get_json() == []
    assert client.get(f"/products/{product_id}").get_json() == before


def test_low_stock_notification_failure_preserves_outgoing_transaction(
    client, product_id, monkeypatch
):
    monkeypatch.setattr(
        "app.routes.transactions.send_notification",
        lambda recipient, subject, message: False,
    )
    movement = {"product_id": product_id, "type": "OUT", "quantity": 5}

    response = client.post("/transactions", json=movement)

    assert response.status_code == 201
    result = response.get_json()
    assert result.pop("notification_sent") is False
    assert {key: result[key] for key in movement} == movement
    stock = client.get(f"/products/{product_id}/stock-level").get_json()
    assert stock["quantity_on_hand"] == 5
    assert client.get("/transactions").get_json() == [result]


def test_outgoing_transaction_above_reorder_level_sends_no_notification(
    client, product_id
):
    movement = {"product_id": product_id, "type": "OUT", "quantity": 4}
    with patch("app.routes.transactions.send_notification") as mock_send:
        response = client.post("/transactions", json=movement)

    assert response.status_code == 201
    result = response.get_json()
    assert "notification_sent" not in result
    assert {key: result[key] for key in movement} == movement
    stock = client.get(f"/products/{product_id}/stock-level").get_json()
    assert stock["quantity_on_hand"] == 6
    assert client.get("/transactions").get_json() == [result]
    mock_send.assert_not_called()
