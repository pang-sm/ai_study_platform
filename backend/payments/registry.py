import os
from .mock import MockPaymentProvider


def is_production_runtime() -> bool:
    return os.getenv("APP_ENV", "").strip().lower() in {"production", "prod"}


def is_mock_payment_allowed() -> bool:
    """Mock is intentionally absent from staging/unknown hosted runtimes."""
    return os.getenv("APP_ENV", "local").strip().lower() in {"", "local", "development", "dev", "test", "testing"}


def get_payment_provider():
    # Real adapters are deliberately opt-in additions once an approved merchant
    # account and sandbox credentials exist. Never infer one from a secret.
    configured = os.getenv("PAYMENT_PROVIDER", "mock").strip().lower()
    if configured == "mock":
        return MockPaymentProvider()
    raise RuntimeError("No approved payment provider adapter is configured")
