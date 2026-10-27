"""Yuxuan Lu's existing-feature tests: P1-P7 and O1-O4 in Table B.

Requirements: R2 (low-stock detection), R3 (manual entry), R5/R6 (stock
records and accuracy), R7 (delivery records), and R16 (stock correction).
The supplied client fixture resets the in-memory store before every test.
"""

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
    """P1: listing identifies both products without losing their saved fields."""
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
    """P2: manual input survives a subsequent detail request (R3/R5)."""
    product = create_product(client)
    response = client.get(f"/products/{product['id']}")
    assert response.status_code == 200
    assert response.get_json() == product


def test_create_product_defaults_optional_numeric_fields_to_zero(client):
    """P2: a product can start without price, stock or a reorder threshold."""
    response = client.post("/products", json={"name": "New Item", "sku": "NEW-001"})
    assert response.status_code == 201
    product = response.get_json()
    assert product == {
        "id": product["id"], "name": "New Item", "sku": "NEW-001",
        "unit_price": 0.0, "quantity_on_hand": 0, "reorder_level": 0,
    }
    assert client.get(f"/products/{product['id']}").get_json() == product


def test_get_product_selects_requested_record_without_changing_others(client):
    """P3: fetching one of several items returns that item and leaves the list intact."""
    first = create_product(client)
    second = create_product(client, name="Screwdriver", sku="SCREW-001")
    response = client.get(f"/products/{second['id']}")
    assert response.status_code == 200
    assert response.get_json() == second
    assert client.get(f"/products/{first['id']}").get_json() == first
    assert len(client.get("/products").get_json()) == 2


def test_update_product_persists_every_supported_field(client):
    """P4: metadata and corrected on-hand stock are saved (R5/R6/R16)."""
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
    """P4: zero is a valid correction, not an instruction to keep the old quantity."""
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
    """P4: an empty partial update does not erase existing fields."""
    product = create_product(client)
    response = client.put(f"/products/{product['id']}", json={})
    assert response.status_code == 200
    assert response.get_json() == product
    assert client.get(f"/products/{product['id']}").get_json() == product


def test_delete_product_removes_it_from_detail_and_list_only(client):
    """P5: deletion is observable and does not remove an unrelated product."""
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
    """P3-P5: nonexistent IDs return an explanation and leave inventory intact."""
    product = create_product(client)
    kwargs = {"json": {"name": "Must Not Be Created"}} if method == "PUT" else {}
    response = client.open("/products/9999", method=method, **kwargs)
    assert response.status_code == 404
    assert response.get_json() == {"error": "Product not found"}
    assert client.get("/products").get_json() == [product]


def test_product_form_manual_entry_is_visible_in_ui_and_api(client):
    """P2 UI: entered quantities and labels appear after the redirect and in the API."""
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
    """P5 UI: the delete button's route removes the same item seen through the API."""
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
