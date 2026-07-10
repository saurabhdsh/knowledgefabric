"""External billing integration stub."""


class BillingClient:
    """Talks to an external payment provider (stub)."""

    def charge(self, customer_id: str, amount: float) -> dict:
        return {
            "customer_id": customer_id,
            "amount": amount,
            "status": "authorized",
            "provider": "demo-pay",
        }
