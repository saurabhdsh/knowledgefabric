"""Domain service for orders."""


class Order:
    def __init__(self, order_id: str, customer_id: str, amount: float):
        self.order_id = order_id
        self.customer_id = customer_id
        self.amount = amount

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "amount": self.amount,
        }


class OrderService:
    def __init__(self):
        self._orders = {
            "ord_100": Order("ord_100", "cust_9", 42.50),
            "ord_200": Order("ord_200", "cust_3", 19.99),
        }

    def get_order(self, order_id: str) -> dict:
        order = self._orders.get(order_id)
        if not order:
            return {"order_id": order_id, "customer_id": "unknown", "amount": 0.0}
        return order.to_dict()
