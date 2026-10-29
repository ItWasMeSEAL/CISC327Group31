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


@pytest.mark.skip(reason="The system runs locally over flask, this cannot be tested.")
def test_r10_long_timeout_on_slow_connection():
    # R10 cannot be tested on a flask client setup, the requirement is skipped and the reason is outputted.
    pass

@pytest.mark.skip(reason="There is no scanner integration built into the system, and no physical scanner to test it with anyways.")
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
