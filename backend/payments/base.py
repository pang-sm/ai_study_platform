from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class VerifiedPaymentEvent:
    provider: str
    provider_event_id: str
    order_no: str
    provider_transaction_id: str
    event_type: str
    amount: int
    currency: str
    verified: bool
    metadata: dict[str, Any]


class PaymentProvider(Protocol):
    name: str
    def create_payment(self, *, order_no: str, amount: int, currency: str) -> dict: ...
    def verify_callback(self, payload: dict, headers: dict | None = None, raw_body: bytes | None = None) -> VerifiedPaymentEvent: ...
    def query_payment(self, provider_transaction_id: str) -> dict: ...
    def refund(self, *, provider_transaction_id: str, amount: int, refund_no: str) -> dict: ...
    def query_refund(self, provider_refund_id: str) -> dict: ...
