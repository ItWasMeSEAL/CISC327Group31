import pytest

'''
Checking functional requirements 10-17.
'''
def make_product(client, sku="TEST-1", quantity=20):
    # Setup code for making a sample product. Not a test.
    payload = dict(name=f"Product {sku}", sku=sku, unit_price=2.5,
                   quantity_on_hand=quantity, reorder_level=2)
    response = client.post("/products", json=payload)
    assert response.status_code == 201
    return response.get_json()


def make_supplier(client, name="Supplier A"):
    # Setup code for making a sample supplier. Not a test.
    response = client.post("/suppliers", json={"name": name, "contact_email": "test@example.com"})
    assert response.status_code == 201
    return response.get_json()


def record(client, product, kind, quantity, supplier=None):
    # Setup code for stock movements, recieving or outgoing. Not a test.
    payload = {"product_id": product["id"], "type": kind, "quantity": quantity}
    if supplier is not None:
        payload["supplier_id"] = supplier["id"]
    response = client.post("/transactions", json=payload)
    assert response.status_code == 201
    return response.get_json()


@pytest.mark.skip(reason="R10: The system runs locally over flask, this cannot be tested.")
def test_r10_long_timeout_on_slow_connection():
    # R10 cannot be tested on a flask client setup, the requirement is skipped and the reason is outputted.
    pass

@pytest.mark.skip(reason="R11: There is no scanner integration built into the system, and no physical scanner to test it with anyways.")
def test_r11_scan_receives_shipment_without_extra_confirmation():
    # There's no way to confirm if the system works with the scanner without real external hardware.
    pass

def test_r12_manual_small_adjustment_needs_no_scanner(client):
    # This function determines if stock amount can be updated manually.
    p = make_product(client, quantity=10)
    response = client.put(f"/products/{p['id']}", json={"quantity_on_hand": 9})
    assert response.status_code == 200
    assert response.get_json()["quantity_on_hand"] == 9
    assert client.get(f"/products/{p['id']}/stock-level").get_json()["quantity_on_hand"] == 9


@pytest.mark.skip(reason="R13: Lack of external information.")
def test_r13_hardware_cost_and_memory_below_spreadsheet():
    # There's no way to know the hardware requirements and how they would compare to the current setup of the fictional company.
    # Same with comparing to existing spreadsheet.
    pass

def test_r14_outgoing_records_retain_product_and_quantity(client):
    # Trying to save which product has the highest volume outgoing.
    p = make_product(client)
    tx = record(client, p, "OUT", 3)
    rows = client.get("/transactions").get_json()
    saved = next(row for row in rows if row["id"] == tx["id"])
    assert saved["product_id"] == p["id"]
    assert saved["type"] == "OUT"
    assert saved["quantity"] == 3
    assert saved["transaction_date"]
    assert client.get(f"/products/{p['id']}/stock-level").get_json()["quantity_on_hand"] == 17


def test_r15_incoming_records_retain_supplier(client):
    # Trying to save which supplier has the highest volume incoming.
    p, s = make_product(client), make_supplier(client)
    tx = record(client, p, "IN", 4, s)
    saved = next(t for t in client.get("/transactions").get_json() if t["id"] == tx["id"])
    assert saved["supplier_id"] == s["id"]
    assert saved["product_id"] == p["id"]
    assert saved["type"] == "IN" and saved["quantity"] == 4
    assert client.get(f"/products/{p['id']}/stock-level").get_json()["quantity_on_hand"] == 24


@pytest.mark.parametrize("actual", [0, 7, 25])
def test_r16_correct_recorded_stock_to_shelf_count(client, actual):
    # By parametrizing, this function can be run multiple times with differing variable values.
    # This function checks if an item's stock quantity value can be updated, in a situation where it differs from the real-world amount.
    original = make_product(client, quantity=12)
    response = client.put(f"/products/{original['id']}", json={"quantity_on_hand": actual})
    assert response.status_code == 200
    assert response.get_json()["quantity_on_hand"] == actual
    saved = client.get(f"/products/{original['id']}").get_json()
    assert saved == {**original, "quantity_on_hand": actual}
    assert client.get(f"/products/{original['id']}/stock-level").get_json()["quantity_on_hand"] == actual


def test_r17_store_and_operate_on_500_products_and_12_suppliers(client):
    # This function tests the database's capacity and if it can handle the specified amount of concurrent products and suppliers.
    products = [make_product(client, f"CAP-{i:03d}", i) for i in range(500)]
    suppliers = [make_supplier(client, f"Supplier {i}") for i in range(12)]
    listed_p = client.get("/products").get_json()
    listed_s = client.get("/suppliers").get_json()
    assert len(listed_p) == 500 and len(listed_s) == 12
    assert {p["id"]: p for p in listed_p} == {p["id"]: p for p in products}
    assert {s["id"]: s for s in listed_s} == {s["id"]: s for s in suppliers}
    for p in (products[0], products[249], products[-1]):
        assert client.get(f"/products/{p['id']}").get_json() == p
    record(client, products[-1], "IN", 3, suppliers[-1])
    assert client.get(f"/products/{products[-1]['id']}/stock-level").get_json()["quantity_on_hand"] == 502
    assert len(client.get("/products").get_json()) == 500

'''
Checking functionality related to suppliers.
'''
def test_supplier_list_creation_and_retrieval(client):
    # This function checks if suppliers can be created, listed and accessed individually.
    # It also checks that each supplier has a different ID and the correct information.
    assert client.get("/suppliers").get_json() == []
    a, b = make_supplier(client, "Alpha"), make_supplier(client, "Beta")
    assert a["id"] != b["id"]
    assert a["name"] == "Alpha" and a["contact_email"] == "test@example.com"
    assert client.get(f"/suppliers/{a['id']}").get_json() == a
    assert {s["id"] for s in client.get("/suppliers").get_json()} == {a["id"], b["id"]}


def test_supplier_partial_update_preserves_name(client):
    # This function checks if a supplier's email can be updated without changing its name.
    s = make_supplier(client)
    r = client.put(f"/suppliers/{s['id']}", json={"contact_email": "new@example.com"})
    assert r.status_code == 200
    assert client.get(f"/suppliers/{s['id']}").get_json() == {**s, "contact_email": "new@example.com"}


def test_supplier_delete_removes_only_selected_supplier(client):
    # This function checks if a supplier can be deleted without deleting another supplier.
    # Trying to access the deleted supplier should return an error.
    a, b = make_supplier(client, "A"), make_supplier(client, "B")
    assert client.delete(f"/suppliers/{a['id']}").status_code == 204
    assert client.get(f"/suppliers/{a['id']}").get_json() == {"error": "Supplier not found"}
    assert client.get("/suppliers").get_json() == [b]


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_supplier_unknown_id(client, method):
    # By parametrizing, this function tests viewing, updating and deleting a supplier that does not exist.
    # Each operation should return HTTP 404 and a message saying the supplier was not found.
    r = getattr(client, method)("/suppliers/9999", **({"json": {"name": "New"}} if method == "put" else {}))
    assert r.status_code == 404
    assert r.get_json() == {"error": "Supplier not found"}


def test_supplier_products_include_only_distinct_received_products(client):
    # This function checks if a supplier's product list only contains products received from that supplier.
    # Receiving the same product twice should not duplicate it, and outgoing transactions should not add products to the list.
    a, b = make_supplier(client, "A"), make_supplier(client, "B")
    p, q = make_product(client, "P"), make_product(client, "Q")
    record(client, p, "IN", 2, a)
    record(client, p, "IN", 3, a)
    record(client, q, "IN", 1, b)
    record(client, q, "OUT", 1, a)
    rows = client.get(f"/suppliers/{a['id']}/products").get_json()
    assert len(rows) == 1 and rows[0]["id"] == p["id"]
    assert rows[0]["quantity_on_hand"] == 25


    '''
    Checking functionality related to transactions.
    '''
def test_outgoing_stock_can_reach_zero(client):
    # This function checks if removing all available units leaves the product with zero stock.
    p = make_product(client, quantity=2)
    record(client, p, "OUT", 2)
    assert client.get(f"/products/{p['id']}/stock-level").get_json()["quantity_on_hand"] == 0


def test_invalid_transaction_type_leaves_stock_and_history_unchanged(client):
    # This function checks if a transaction with an invalid type is rejected.
    # The rejected transaction should not change the stock quantity or appear in transaction history.
    p = make_product(client)
    r = client.post("/transactions", json={"product_id": p["id"], "type": "INVALID", "quantity": 2})
    assert r.status_code == 400
    assert r.get_json()["error"] == "type must be IN or OUT"
    assert client.get("/transactions").get_json() == []
    assert client.get(f"/products/{p['id']}/stock-level").get_json()["quantity_on_hand"] == 20


def test_missing_transaction_product_does_not_create_history(client):
    # This function checks if a transaction for a product that does not exist is rejected.
    # It should return HTTP 404 without adding anything to transaction history.
    r = client.post("/transactions", json={"product_id": 9999, "type": "IN", "quantity": 1})
    assert r.status_code == 404
    assert r.get_json() == {"error": "Product not found"}
    assert client.get("/transactions").get_json() == []


def test_transaction_history_filters_by_supplier(client):
    # This function checks if filtering by a supplier only returns that supplier's transactions.
    # Two suppliers are used so transactions from the other supplier should be excluded.
    a, b = make_supplier(client, "A"), make_supplier(client, "B")
    p = make_product(client)
    expected = record(client, p, "IN", 1, a)
    record(client, p, "IN", 1, b)
    assert client.get(f"/transactions?supplier_id={a['id']}").get_json() == [expected]


def test_transaction_history_filters_by_product_not_supplier(client):
    # This function checks if filtering by a product only returns transactions for that product.
    # Different product and supplier IDs are used to expose a bug where the filter checks the supplier ID instead.
    other, wanted = make_product(client, "OTHER"), make_product(client, "WANTED")
    supplier = make_supplier(client)
    expected = record(client, wanted, "IN", 1, supplier)
    record(client, other, "IN", 1, supplier)
    assert wanted["id"] != supplier["id"]
    assert client.get(f"/transactions?product_id={wanted['id']}").get_json() == [expected]


def test_home_page_contains_inventory_navigation(client):
    # This function checks if the home page loads with the correct heading.
    # It also checks that links to the products, suppliers and transactions pages are present.
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Inventory Management System" in html
    for path in ("/ui/products", "/ui/suppliers", "/ui/transactions"):
        assert f'href="{path}"' in html




def test_transaction_history_filters_by_product_and_supplier(client):
    # This function checks if using both filters only returns transactions matching both IDs.
    # Transactions matching only the product or only the supplier should be excluded.
    other, wanted = make_product(client, "OTHER"), make_product(client, "WANTED")
    supplier_a = make_supplier(client, "Supplier A")
    supplier_b = make_supplier(client, "Supplier B")

    expected = record(client, wanted, "IN", 3, supplier_a)
    record(client, wanted, "IN", 2, supplier_b)
    record(client, other, "IN", 4, supplier_a)

    response = client.get(
        f"/transactions?product_id={wanted['id']}"
        f"&supplier_id={supplier_a['id']}"
    )

    assert response.status_code == 200
    assert response.get_json() == [expected]


def test_product_filter_does_not_match_supplier_id(client):
    # This function checks that a supplier ID matching the requested product ID does not cause an incorrect match.
    # The requested product has no transactions, so the result should be empty.
    wanted = make_product(client, "WANTED")
    other = make_product(client, "OTHER")
    supplier = make_supplier(client)

    assert wanted["id"] == supplier["id"]
    assert other["id"] != wanted["id"]

    transaction = record(client, other, "IN", 3, supplier)

    response = client.get(
        f"/transactions?product_id={wanted['id']}"
    )

    assert response.status_code == 200
    assert response.get_json() == []

    # Check that the transaction still exists and was only excluded by the filter.
    assert client.get("/transactions").get_json() == [transaction]
