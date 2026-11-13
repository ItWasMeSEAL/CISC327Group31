from unittest.mock import patch


def make_a3_product(client, sku="A3-001", quantity=8, reorder_level=5):
    # Setup code for creating a test product. Not a test.
    response = client.post("/products", json={
        "name": f"Product {sku}",
        "sku": sku,
        "unit_price": 10.0,
        "quantity_on_hand": quantity,
        "reorder_level": reorder_level,
    })

    assert response.status_code == 201
    return response.get_json()


def make_a3_supplier(client, name, email):
    # Setup code for creating a test supplier. Not a test.
    response = client.post("/suppliers", json={
        "name": name,
        "contact_email": email,
    })

    assert response.status_code == 201
    return response.get_json()


def test_low_stock_alert_success_with_stub(client, monkeypatch):
    # Simulate a successful notification without calling the real service.
    monkeypatch.setattr(
        "app.routes.transactions.send_notification",
        lambda recipient, subject, message: True,
    )

    # Create a product with 8 units and a reorder level of 5.
    product = make_a3_product(
        client, sku="STUB-001", quantity=8, reorder_level=5
    )

    # Remove 4 units, bringing the stock down to 4.
    response = client.post("/transactions", json={
        "product_id": product["id"],
        "type": "OUT",
        "quantity": 4,
    })

    # Check that the transaction succeeded and notification succeeded.
    assert response.status_code == 201
    assert response.get_json()["notification_sent"] is True

    # Check that inventory was updated correctly.
    saved_product = client.get(
        f"/products/{product['id']}"
    ).get_json()

    assert saved_product["quantity_on_hand"] == 4

    # The product should now appear in the low-stock list.
    assert client.get("/products/low-stock").get_json() == [
        saved_product
    ]

    # Check that the transaction was recorded.
    history = client.get("/transactions").get_json()

    assert len(history) == 1
    assert history[0]["product_id"] == product["id"]
    assert history[0]["type"] == "OUT"
    assert history[0]["quantity"] == 4
    assert response.get_json()["id"] == history[0]["id"]


def test_low_stock_alert_correct_arguments_with_mock(client):
    # Create a product with 9 units and a reorder level of 5.
    product = make_a3_product(
        client, sku="MOCK-001", quantity=9, reorder_level=5
    )

    # Replace the notification service with a mock.
    with patch(
        "app.routes.transactions.send_notification",
        return_value=True
    ) as mock_send:

        # Remove 5 units, bringing stock down to 4.
        response = client.post("/transactions", json={
            "product_id": product["id"],
            "type": "OUT",
            "quantity": 5,
        })

    # Check that the transaction completed successfully.
    assert response.status_code == 201
    assert response.get_json()["notification_sent"] is True

    # Check the new product quantity.
    saved_product = client.get(
        f"/products/{product['id']}"
    ).get_json()

    assert saved_product["quantity_on_hand"] == 4

    # Check that the transaction was recorded.
    assert len(client.get("/transactions").get_json()) == 1

    # Check the exact notification arguments and call count.
    mock_send.assert_called_once_with(
        "inventory-staff",
        "[Harborview Inventory] Low-stock alert",
        "Product MOCK-001 is low on stock. Only 4 units remain."
    )
