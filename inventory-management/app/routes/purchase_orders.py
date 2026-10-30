from datetime import date

from flask import Blueprint, jsonify, request

from app import store
from app.models.purchase_order import PurchaseOrder
from app.models.transaction import Transaction

purchase_orders_bp = Blueprint("purchase_orders", __name__, url_prefix="/purchase-orders")


@purchase_orders_bp.route("", methods=["GET"])
def list_purchase_orders():
    return jsonify([po.to_dict() for po in store.purchase_orders.values()])


@purchase_orders_bp.route("", methods=["POST"])
def create_purchase_order():
    data = request.get_json()
    supplier = store.suppliers.get(data["supplier_id"])
    if supplier is None:
        return jsonify({"error": "Supplier not found"}), 404
    product = store.products.get(data["product_id"])
    if product is None:
        return jsonify({"error": "Product not found"}), 404

    po_id = store.next_id("purchase_order")
    po = PurchaseOrder(
        id=po_id,
        supplier_id=data["supplier_id"],
        product_id=data["product_id"],
        quantity_ordered=data["quantity_ordered"],
        status="pending",
    )
    store.purchase_orders[po_id] = po
    return jsonify(po.to_dict()), 201


@purchase_orders_bp.route("/<int:po_id>", methods=["GET"])
def get_purchase_order(po_id):
    po = store.purchase_orders.get(po_id)
    if po is None:
        return jsonify({"error": "Purchase order not found"}), 404
    return jsonify(po.to_dict())


@purchase_orders_bp.route("/<int:po_id>/receive", methods=["PUT"])
def receive_purchase_order(po_id):
    po = store.purchase_orders.get(po_id)
    if po is None:
        return jsonify({"error": "Purchase order not found"}), 404
    if po.status == "received":
        return jsonify({"error": "Purchase order already received"}), 400

    product = store.products.get(po.product_id)
    if product is None:
        return jsonify({"error": "Product not found"}), 404

    po.status = "received"
    po.received_date = date.today()

    # Record the incoming stock as a transaction so there is an audit trail.
    transaction_id = store.next_id("transaction")
    transaction = Transaction(
        id=transaction_id,
        product_id=po.product_id,
        supplier_id=po.supplier_id,
        type="IN",
        quantity=po.quantity_ordered,
    )
    store.transactions[transaction_id] = transaction
    product.quantity_on_hand += po.quantity_ordered

    return jsonify(po.to_dict())
