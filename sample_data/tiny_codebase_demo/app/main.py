"""Demo API entrypoint for codebase fabric testing."""
from flask import Flask, jsonify

from app.orders import OrderService
from app.billing import BillingClient

app = Flask(__name__)
orders = OrderService()
billing = BillingClient()


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/orders/<order_id>")
def get_order(order_id: str):
    return jsonify(orders.get_order(order_id))


@app.post("/orders/<order_id>/pay")
def pay_order(order_id: str):
    order = orders.get_order(order_id)
    result = billing.charge(order["customer_id"], order["amount"])
    return jsonify({"order_id": order_id, "payment": result})


if __name__ == "__main__":
    app.run(port=5055)
