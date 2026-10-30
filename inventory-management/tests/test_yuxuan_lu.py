"""Existing-feature tests: P1-P7 and O1-O4 in Table B.

Requirements: R2, R3, R5/R6, R7, and R16.
"""

from datetime import date

import pytest


def create_product(client, **overrides):
    payload = {
        "name": "Claw Hammer",
        "sku": "HAM-001",
        "unit_price": 19.95,
        "quantity_on_hand": 10,
        "reorder_level": 3,
    }
    payload.update(overrides)
    response = client.post("/products", json=payload)
    assert response.status_code == 201
    product = response.get_json()
    assert isinstance(product["id"], int)
    assert product["id"] > 0
    assert product == {"id": product["id"], **payload}
    return product


def test_list_products_preserves_fields_and_distinct_records(client):
    # Check the list contains both products with their saved details.
    hammer = create_product(client)
    nails = create_product(
        client, name="Box of Nails", sku="NAIL-001", unit_price=4.5,
        quantity_on_hand=25, reorder_level=5,
    )
    response = client.get("/products")
    assert response.status_code == 200
    listed = response.get_json()
    assert len(listed) == 2
    assert hammer["id"] != nails["id"]
    assert {p["id"]: p for p in listed} == {
        hammer["id"]: hammer, nails["id"]: nails,
    }


def test_create_product_persists_all_entered_fields(client):
    # Check a new product keeps all entered values.
    product = create_product(client)
    response = client.get(f"/products/{product['id']}")
    assert response.status_code == 200
    assert response.get_json() == product


def test_create_product_defaults_optional_numeric_fields_to_zero(client):
    # Check optional numeric fields default to zero.
    response = client.post("/products", json={"name": "New Item", "sku": "NEW-001"})
    assert response.status_code == 201
    product = response.get_json()
    assert product == {
        "id": product["id"], "name": "New Item", "sku": "NEW-001",
        "unit_price": 0.0, "quantity_on_hand": 0, "reorder_level": 0,
    }
    assert client.get(f"/products/{product['id']}").get_json() == product


def test_get_product_selects_requested_record_without_changing_others(client):
    # Check getting one product leaves other products unchanged.
    first = create_product(client)
    second = create_product(client, name="Screwdriver", sku="SCREW-001")
    response = client.get(f"/products/{second['id']}")
    assert response.status_code == 200
    assert response.get_json() == second
    assert client.get(f"/products/{first['id']}").get_json() == first
    assert len(client.get("/products").get_json()) == 2


def test_update_product_persists_every_supported_field(client):
    # Check all product fields can be updated.
    product = create_product(client)
    changes = {
        "name": "Updated Hammer", "sku": "HAM-002", "unit_price": 22.5,
        "quantity_on_hand": 17, "reorder_level": 6,
    }
    response = client.put(f"/products/{product['id']}", json=changes)
    expected = {"id": product["id"], **changes}
    assert response.status_code == 200
    assert response.get_json() == expected
    assert client.get(f"/products/{product['id']}").get_json() == expected


def test_update_product_to_zero_keeps_omitted_fields_and_other_products(client):
    # Check zero updates preserve omitted fields and other products.
    product = create_product(client)
    other = create_product(client, name="Tape Measure", sku="TAPE-001")
    changes = {"quantity_on_hand": 0, "unit_price": 0, "reorder_level": 0}
    response = client.put(f"/products/{product['id']}", json=changes)
    expected = {**product, **changes}
    assert response.status_code == 200
    assert response.get_json() == expected
    assert client.get(f"/products/{product['id']}").get_json() == expected
    assert client.get(f"/products/{other['id']}").get_json() == other


def test_empty_product_update_preserves_saved_record(client):
    # Check an empty update leaves the product unchanged.
    product = create_product(client)
    response = client.put(f"/products/{product['id']}", json={})
    assert response.status_code == 200
    assert response.get_json() == product
    assert client.get(f"/products/{product['id']}").get_json() == product


def test_delete_product_removes_it_from_detail_and_list_only(client):
    # Check deletion removes only the selected product.
    product = create_product(client)
    other = create_product(client, name="Spanner", sku="SPAN-001")
    response = client.delete(f"/products/{product['id']}")
    assert response.status_code == 204
    assert response.data == b""
    missing = client.get(f"/products/{product['id']}")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "Product not found"}
    assert client.get("/products").get_json() == [other]
    repeated = client.delete(f"/products/{product['id']}")
    assert repeated.status_code == 404
    assert repeated.get_json() == {"error": "Product not found"}
    assert client.get("/products").get_json() == [other]


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_missing_product_operations_do_not_change_existing_records(client, method):
    # Check missing product IDs return an error without changing inventory.
    product = create_product(client)
    kwargs = {"json": {"name": "Must Not Be Created"}} if method == "PUT" else {}
    response = client.open("/products/9999", method=method, **kwargs)
    assert response.status_code == 404
    assert response.get_json() == {"error": "Product not found"}
    assert client.get("/products").get_json() == [product]


def test_product_form_manual_entry_is_visible_in_ui_and_api(client):
    # Check a product added through the form appears in the UI and API.
    response = client.post("/ui/products", data={
        "name": "Manual Entry Drill", "sku": "MANUAL-001",
        "unit_price": "39.95", "quantity_on_hand": "7",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == "/ui/products"
    assert b"Manual Entry Drill" in response.data
    assert b"MANUAL-001" in response.data
    products = client.get("/products").get_json()
    assert len(products) == 1
    product = products[0]
    assert product == {
        "id": product["id"], "name": "Manual Entry Drill", "sku": "MANUAL-001",
        "unit_price": 39.95, "quantity_on_hand": 7, "reorder_level": 0,
    }
    assert client.get(f"/products/{product['id']}").get_json() == product


def test_product_form_delete_removes_target_and_preserves_other_item(client):
    # Check the delete form removes only the selected product.
    product = create_product(client)
    other = create_product(client, name="Remaining Item", sku="REMAIN-001")
    response = client.post(
        f"/ui/products/{product['id']}/delete", follow_redirects=True,
    )
    assert response.status_code == 200
    assert response.request.path == "/ui/products"
    assert b"HAM-001" not in response.data
    assert b"REMAIN-001" in response.data
    assert client.get("/products").get_json() == [other]
    assert client.get(f"/products/{product['id']}").status_code == 404


def test_stock_level_follows_incoming_outgoing_and_zero_balance(client):
    # Check stock changes after receipts and withdrawals, including zero stock.
    product = create_product(client)
    pid = product["id"]
    other = create_product(client, name="Unchanged Item", sku="OTHER-001")
    stock = client.get(f"/products/{pid}/stock-level")
    assert stock.status_code == 200
    assert stock.get_json() == {"product_id": pid, "quantity_on_hand": 10}

    for tx_type, quantity, expected in [("IN", 5, 15), ("OUT", 3, 12), ("OUT", 12, 0)]:
        response = client.post("/transactions", json={
            "product_id": pid, "type": tx_type, "quantity": quantity,
        })
        assert response.status_code == 201
        assert response.get_json()["product_id"] == pid
        stock = client.get(f"/products/{pid}/stock-level")
        assert stock.status_code == 200
        assert stock.get_json() == {"product_id": pid, "quantity_on_hand": expected}
        assert client.get(f"/products/{pid}").get_json()["quantity_on_hand"] == expected
        assert client.get(f"/products/{other['id']}").get_json() == other


def test_stock_level_reflects_manual_quantity_correction(client):
    # Check a manual stock correction appears in later reads.
    product = create_product(client)
    pid = product["id"]
    response = client.put(f"/products/{pid}", json={"quantity_on_hand": 4})
    assert response.status_code == 200
    assert response.get_json() == {**product, "quantity_on_hand": 4}
    stock = client.get(f"/products/{pid}/stock-level")
    assert stock.status_code == 200
    assert stock.get_json() == {"product_id": pid, "quantity_on_hand": 4}
    assert client.get("/products").get_json() == [{**product, "quantity_on_hand": 4}]


def test_stock_level_for_missing_product_preserves_inventory(client):
    # Check a missing product has no stock level and leaves inventory unchanged.
    product = create_product(client)
    response = client.get("/products/9999/stock-level")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Product not found"}
    assert client.get("/products").get_json() == [product]


@pytest.mark.parametrize("quantity,expected_low", [(0, True), (2, True), (3, True), (4, False)])
def test_low_stock_includes_zero_below_and_equal_threshold_only(client, quantity, expected_low):
    # Check low-stock results at zero, below, equal to and above the threshold.
    product = create_product(client, quantity_on_hand=quantity, reorder_level=3)
    response = client.get("/products/low-stock")
    assert response.status_code == 200
    assert response.get_json() == ([product] if expected_low else [])
    assert client.get(f"/products/{product['id']}").get_json() == product


def test_low_stock_empty_inventory_has_no_alert_candidates(client):
    # Check empty inventory returns no low-stock products.
    response = client.get("/products/low-stock")
    assert response.status_code == 200
    assert response.get_json() == []
    assert client.get("/products").get_json() == []


def test_low_stock_selects_each_products_own_reorder_level(client):
    # Check each product uses its own reorder level.
    low = create_product(client, quantity_on_hand=8, reorder_level=10)
    high = create_product(client, name="High Stock", sku="HIGH-001", quantity_on_hand=8, reorder_level=2)
    equal = create_product(client, name="At Threshold", sku="EQUAL-001", quantity_on_hand=5, reorder_level=5)
    response = client.get("/products/low-stock")
    assert response.status_code == 200
    found = response.get_json()
    assert len(found) == 2
    assert {p["id"]: p for p in found} == {low["id"]: low, equal["id"]: equal}
    assert client.get(f"/products/{high['id']}").get_json() == high


def test_low_stock_recomputes_after_movements_and_threshold_updates(client):
    # Check low-stock results update after stock and threshold changes.
    product = create_product(client, quantity_on_hand=4, reorder_level=3)
    pid = product["id"]
    assert client.get("/products/low-stock").get_json() == []
    out = client.post("/transactions", json={"product_id": pid, "type": "OUT", "quantity": 1})
    assert out.status_code == 201
    assert client.get("/products/low-stock").get_json() == [{**product, "quantity_on_hand": 3}]
    incoming = client.post("/transactions", json={"product_id": pid, "type": "IN", "quantity": 2})
    assert incoming.status_code == 201
    assert client.get("/products/low-stock").get_json() == []
    update = client.put(f"/products/{pid}", json={"reorder_level": 5})
    expected = {**product, "quantity_on_hand": 5, "reorder_level": 5}
    assert update.status_code == 200
    assert update.get_json() == expected
    assert client.get("/products/low-stock").get_json() == [expected]
    assert client.delete(f"/products/{pid}").status_code == 204
    assert client.get("/products/low-stock").get_json() == []


def create_supplier(client, name="Hardware Supplier", email="orders@example.com"):
    response = client.post("/suppliers", json={"name": name, "contact_email": email})
    assert response.status_code == 201
    supplier = response.get_json()
    assert supplier == {"id": supplier["id"], "name": name, "contact_email": email}
    return supplier


def create_purchase_order(client, product, supplier, quantity=4):
    before = date.today()
    payload = {
        "product_id": product["id"], "supplier_id": supplier["id"],
        "quantity_ordered": quantity,
    }
    response = client.post("/purchase-orders", json=payload)
    assert response.status_code == 201
    order = response.get_json()
    assert order == {
        "id": order["id"], **payload, "status": "pending",
        "created_date": order["created_date"], "received_date": None,
    }
    assert isinstance(order["id"], int)
    assert order["id"] > 0
    assert before <= date.fromisoformat(order["created_date"]) <= date.today()
    return order


def test_list_purchase_orders_initially_empty_without_altering_stock(client):
    # Check the order list starts empty without changing stock.
    product = create_product(client)
    response = client.get("/purchase-orders")
    assert response.status_code == 200
    assert response.get_json() == []
    assert client.get(f"/products/{product['id']}").get_json() == product


def test_create_purchase_order_persists_pending_state_without_receiving_stock(client):
    # Check creating an order saves it as pending without adding stock.
    product = create_product(client)
    supplier = create_supplier(client)
    order = create_purchase_order(client, product, supplier, quantity=4)
    response = client.get(f"/purchase-orders/{order['id']}")
    assert response.status_code == 200
    assert response.get_json() == order
    assert client.get("/purchase-orders").get_json() == [order]
    assert client.get(f"/products/{product['id']}").get_json() == product
    assert client.get("/transactions").get_json() == []


def test_list_and_get_purchase_orders_preserve_distinct_orders(client):
    # Check listing and viewing orders returns the correct details.
    first_product = create_product(client)
    second_product = create_product(client, name="Saw", sku="SAW-001")
    first_supplier = create_supplier(client)
    second_supplier = create_supplier(client, "Second Supplier", "second@example.com")
    first = create_purchase_order(client, first_product, first_supplier, quantity=1)
    second = create_purchase_order(client, second_product, second_supplier, quantity=8)
    response = client.get("/purchase-orders")
    assert response.status_code == 200
    listed = response.get_json()
    assert first["id"] != second["id"]
    assert len(listed) == 2
    assert {po["id"]: po for po in listed} == {first["id"]: first, second["id"]: second}
    for order in [second, first]:
        detail = client.get(f"/purchase-orders/{order['id']}")
        assert detail.status_code == 200
        assert detail.get_json() == order


@pytest.mark.parametrize("missing_field,error", [
    ("supplier_id", "Supplier not found"), ("product_id", "Product not found"),
])
def test_create_purchase_order_rejects_missing_related_ids_without_side_effects(client, missing_field, error):
    # Check orders cannot use nonexistent products or suppliers.
    product = create_product(client)
    supplier = create_supplier(client)
    existing = create_purchase_order(client, product, supplier)
    payload = {"product_id": product["id"], "supplier_id": supplier["id"], "quantity_ordered": 4}
    payload[missing_field] = 9999
    response = client.post("/purchase-orders", json=payload)
    assert response.status_code == 404
    assert response.get_json() == {"error": error}
    assert client.get("/purchase-orders").get_json() == [existing]
    assert client.get(f"/products/{product['id']}").get_json() == product
    assert client.get("/transactions").get_json() == []


def test_get_missing_purchase_order_does_not_change_saved_order(client):
    # Check a missing order returns an error without changing saved orders.
    product = create_product(client)
    supplier = create_supplier(client)
    order = create_purchase_order(client, product, supplier)
    response = client.get("/purchase-orders/9999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Purchase order not found"}
    assert client.get("/purchase-orders").get_json() == [order]


def test_receive_purchase_order_persists_date_and_incoming_audit_record(client):
    # Check receiving an order saves its date and incoming transaction.
    product = create_product(client)
    supplier = create_supplier(client)
    order = create_purchase_order(client, product, supplier)
    before = date.today()
    response = client.put(f"/purchase-orders/{order['id']}/receive")
    assert response.status_code == 200
    received = response.get_json()
    assert received == {**order, "status": "received", "received_date": received["received_date"]}
    assert before <= date.fromisoformat(received["received_date"]) <= date.today()
    assert client.get(f"/purchase-orders/{order['id']}").get_json() == received
    assert client.get("/purchase-orders").get_json() == [received]
    history = client.get("/transactions")
    assert history.status_code == 200
    transactions = history.get_json()
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction == {
        "id": transaction["id"], "product_id": product["id"], "supplier_id": supplier["id"],
        "type": "IN", "quantity": 4, "transaction_date": transaction["transaction_date"],
    }
    assert before <= date.fromisoformat(transaction["transaction_date"]) <= date.today()


def test_receive_purchase_order_increases_product_stock(client):
    # Check receiving four units increases stock from 10 to 14.
    product = create_product(client, quantity_on_hand=10)
    supplier = create_supplier(client)
    order = create_purchase_order(client, product, supplier, quantity=4)
    response = client.put(f"/purchase-orders/{order['id']}/receive")
    assert response.status_code == 200
    assert response.get_json()["status"] == "received"
    detail = client.get(f"/products/{product['id']}")
    stock = client.get(f"/products/{product['id']}/stock-level")
    assert detail.status_code == stock.status_code == 200
    assert detail.get_json()["quantity_on_hand"] == stock.get_json()["quantity_on_hand"]
    assert stock.get_json() == {"product_id": product["id"], "quantity_on_hand": 14}, (
        "R5/R6 receipt-stock defect: 10 on hand + 4 received must equal 14; "
        f"observed {stock.get_json()}"
    )


def test_repeated_receipt_does_not_duplicate_records_or_change_stock_again(client):
    # Check receiving the same order twice does not duplicate stock or records.
    product = create_product(client)
    supplier = create_supplier(client)
    order = create_purchase_order(client, product, supplier)
    first = client.put(f"/purchase-orders/{order['id']}/receive")
    assert first.status_code == 200
    saved_order = first.get_json()
    saved_transactions = client.get("/transactions").get_json()
    assert len(saved_transactions) == 1
    saved_stock = client.get(f"/products/{product['id']}/stock-level").get_json()
    assert saved_stock == {"product_id": product["id"], "quantity_on_hand": 14}
    second = client.put(f"/purchase-orders/{order['id']}/receive")
    assert second.status_code == 400
    assert second.get_json() == {"error": "Purchase order already received"}
    assert client.get(f"/purchase-orders/{order['id']}").get_json() == saved_order
    assert client.get("/transactions").get_json() == saved_transactions
    assert client.get(f"/products/{product['id']}/stock-level").get_json() == saved_stock


def test_receive_missing_purchase_order_leaves_inventory_and_pending_order_intact(client):
    # Check receiving a missing order leaves stock and existing orders unchanged.
    product = create_product(client)
    supplier = create_supplier(client)
    order = create_purchase_order(client, product, supplier)
    response = client.put("/purchase-orders/9999/receive")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Purchase order not found"}
    assert client.get("/purchase-orders").get_json() == [order]
    assert client.get("/transactions").get_json() == []
    assert client.get(f"/products/{product['id']}").get_json() == product


def test_receiving_one_order_keeps_other_order_pending(client):
    # Check receiving one order leaves the other order pending.
    product = create_product(client)
    other_product = create_product(client, name="Pending Product", sku="PENDING-001")
    supplier = create_supplier(client)
    first = create_purchase_order(client, product, supplier, quantity=4)
    pending = create_purchase_order(client, other_product, supplier, quantity=7)
    response = client.put(f"/purchase-orders/{first['id']}/receive")
    assert response.status_code == 200
    received = response.get_json()
    assert received["status"] == "received"
    assert client.get(f"/purchase-orders/{pending['id']}").get_json() == pending
    orders = client.get("/purchase-orders").get_json()
    assert len(orders) == 2
    assert {po["id"]: po for po in orders} == {first["id"]: received, pending["id"]: pending}
    assert client.get(f"/products/{other_product['id']}").get_json() == other_product
    transactions = client.get("/transactions").get_json()
    assert len(transactions) == 1
    assert transactions[0]["product_id"] == product["id"]


@pytest.mark.parametrize("initial,received", [(0, 1), (3, 7)])
def test_receiving_order_adds_stock_and_records_matching_quantity(client, initial, received):
    # Check receiving an order adds its quantity, including initially empty stock.
    product = create_product(client, quantity_on_hand=initial)
    supplier = create_supplier(client)
    order = create_purchase_order(client, product, supplier, quantity=received)
    response = client.put(f"/purchase-orders/{order['id']}/receive")
    assert response.status_code == 200
    saved_order = response.get_json()
    assert saved_order["status"] == "received"
    assert saved_order["quantity_ordered"] == received
    assert saved_order["received_date"] is not None
    assert client.get(f"/purchase-orders/{order['id']}").get_json() == saved_order
    expected_product = {**product, "quantity_on_hand": initial + received}
    assert client.get(f"/products/{product['id']}").get_json() == expected_product
    assert client.get(f"/products/{product['id']}/stock-level").get_json() == {
        "product_id": product["id"], "quantity_on_hand": initial + received,
    }
    transactions = client.get("/transactions").get_json()
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction["product_id"] == product["id"]
    assert transaction["supplier_id"] == supplier["id"]
    assert transaction["type"] == "IN"
    assert transaction["quantity"] == received
    assert transaction["transaction_date"] == saved_order["received_date"]


def test_receiving_two_orders_adds_to_current_stock_only_for_target_product(client):
    # Check separate receipts add together without changing another product.
    product = create_product(client)
    other = create_product(client, name="Other Product", sku="OTHER-RECEIPT")
    supplier = create_supplier(client)
    first = create_purchase_order(client, product, supplier, quantity=4)
    second = create_purchase_order(client, product, supplier, quantity=7)
    for order, expected_stock in [(first, 14), (second, 21)]:
        response = client.put(f"/purchase-orders/{order['id']}/receive")
        assert response.status_code == 200
        assert response.get_json()["status"] == "received"
        assert client.get(f"/products/{product['id']}/stock-level").get_json() == {
            "product_id": product["id"], "quantity_on_hand": expected_stock,
        }
        assert client.get(f"/products/{other['id']}").get_json() == other
    assert client.get(f"/products/{product['id']}").get_json() == {
        **product, "quantity_on_hand": 21,
    }
    transactions = client.get("/transactions").get_json()
    assert len(transactions) == 2
    assert [t["quantity"] for t in sorted(transactions, key=lambda t: t["id"])] == [4, 7]
    assert all(t["product_id"] == product["id"] and t["type"] == "IN" for t in transactions)


def test_receiving_order_for_deleted_product_keeps_order_pending(client):
    # Check a deleted product prevents receipt without changing the order or history.
    product = create_product(client)
    supplier = create_supplier(client)
    order = create_purchase_order(client, product, supplier)
    assert client.delete(f"/products/{product['id']}").status_code == 204
    response = client.put(f"/purchase-orders/{order['id']}/receive")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Product not found"}
    assert client.get(f"/purchase-orders/{order['id']}").get_json() == order
    assert client.get("/purchase-orders").get_json() == [order]
    assert client.get("/transactions").get_json() == []
    assert client.get("/products").get_json() == []
