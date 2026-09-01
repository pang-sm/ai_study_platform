from .base import VerifiedPaymentEvent


class MockPaymentProvider:
    """Deterministic local/test adapter. It is not a payment gateway and has no callback URL."""
    name = "mock"

    def create_payment(self, *, order_no: str, amount: int, currency: str) -> dict:
        return {"provider": self.name, "order_no": order_no, "amount": amount, "currency": currency, "mode": "local_test"}

    def verify_callback(self, payload: dict, headers: dict | None = None, raw_body: bytes | None = None) -> VerifiedPaymentEvent:
        # The local route constructs this payload after authenticated ownership
        # validation. Real adapters MUST cryptographically verify callbacks.
        order_no = str(payload["order_no"])
        return VerifiedPaymentEvent(self.name, f"mock-paid:{order_no}", order_no,
                                    f"mock-txn:{order_no}", "PAYMENT_SUCCEEDED",
                                    int(payload["amount"]), str(payload.get("currency", "CNY")), True, {"mode": "local_test"})

    def query_payment(self, provider_transaction_id: str) -> dict:
        return {"status": "NOT_AVAILABLE_LOCAL"}

    def refund(self, *, provider_transaction_id: str, amount: int, refund_no: str) -> dict:
        return {"status": "NOT_AVAILABLE_LOCAL"}

    def query_refund(self, provider_refund_id: str) -> dict:
        return {"status": "NOT_AVAILABLE_LOCAL"}
