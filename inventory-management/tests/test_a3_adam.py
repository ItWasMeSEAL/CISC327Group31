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


def test_supplier_form_creates_supplier_visible_in_ui_and_api(client):
    # Check that the supplier page loads.
    starting_page = client.get("/ui/suppliers")
    assert starting_page.status_code == 200

    # Submit the form to create a supplier.
    response = client.post("/ui/suppliers", data={
        "name": "Allied Supply",
        "contact_email": "orders@allied.example",
    }, follow_redirects=True)

    # Check that the form redirected back to the supplier page.
    assert response.status_code == 200
    assert response.request.path == "/ui/suppliers"

    # Check that the new supplier is displayed.
    assert b"Allied Supply" in response.data
    assert b"orders@allied.example" in response.data

    # Check that the supplier was saved to the application's store.
    suppliers = client.get("/suppliers").get_json()

    assert len(suppliers) == 1
    assert suppliers[0]["name"] == "Allied Supply"
    assert suppliers[0]["contact_email"] == "orders@allied.example"


def test_supplier_form_deletes_only_selected_supplier(client):
    # Create two suppliers.
    deleted = make_a3_supplier(
        client, "Remove Me", "remove@example.com"
    )
    remaining = make_a3_supplier(
        client, "Keep Me", "keep@example.com"
    )

    # Delete the first supplier through the UI.
    response = client.post(
        f"/ui/suppliers/{deleted['id']}/delete",
        follow_redirects=True,
    )

    # Check that the request returned to the supplier page.
    assert response.status_code == 200
    assert response.request.path == "/ui/suppliers"

    # Check the page displays only the remaining supplier.
    assert b"Keep Me" in response.data
    assert b"Remove Me" not in response.data

    # Check the API also shows that only one supplier remains.
    assert client.get("/suppliers").get_json() == [remaining]

    # Check that the deleted supplier can no longer be retrieved.
    assert client.get(
        f"/suppliers/{deleted['id']}"
    ).status_code == 404


def test_supplier_products_omit_deleted_product_with_old_receipt(client):
    # Create one supplier and two products.
    supplier = make_a3_supplier(
        client, "Parts Supplier", "parts@example.com"
    )
    removed = make_a3_product(client, sku="OLD-001")
    kept = make_a3_product(client, sku="NEW-001")

    # Record an incoming transaction for each product.
    for product in (removed, kept):
        response = client.post("/transactions", json={
            "product_id": product["id"],
            "supplier_id": supplier["id"],
            "type": "IN",
            "quantity": 2,
        })
        assert response.status_code == 201

    # Delete one product, leaving its transaction history behind.
    assert client.delete(
        f"/products/{removed['id']}"
    ).status_code == 204

    # Request the products received from this supplier.
    response = client.get(
        f"/suppliers/{supplier['id']}/products"
    )

    assert response.status_code == 200

    # Only the product that still exists should be returned.
    assert response.get_json() == [
        client.get(f"/products/{kept['id']}").get_json()
    ]

    # The original transaction history should remain unchanged.
    assert len(client.get("/transactions").get_json()) == 2


def test_supplier_products_for_unknown_supplier_returns_404(client):
    # Create an existing product.
    product = make_a3_product(client)

    # Request products for a supplier that does not exist.
    response = client.get("/suppliers/9999/products")

    # Check the error response.
    assert response.status_code == 404
    assert response.get_json() == {
        "error": "Supplier not found"
    }

    # Check that the existing product was not changed.
    assert client.get(
        f"/products/{product['id']}"
    ).get_json() == product
