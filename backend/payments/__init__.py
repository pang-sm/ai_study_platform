"""Provider-neutral payment boundary; adapters must never leak SDK payloads upstream."""
from .base import PaymentProvider, VerifiedPaymentEvent
from .mock import MockPaymentProvider
from .registry import (
    MOCK_PAYMENT_ENVIRONMENTS,
    get_payment_provider,
    is_mock_payment_allowed,
    is_production_runtime,
)

__all__ = ["PaymentProvider", "VerifiedPaymentEvent", "MockPaymentProvider", "get_payment_provider", "is_production_runtime", "is_mock_payment_allowed", "MOCK_PAYMENT_ENVIRONMENTS"]
