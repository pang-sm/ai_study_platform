"""Centralized Product Backend logging configuration (no secrets, no side effects)."""
import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure the root logger once; idempotent across imports/processes."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)
    return root


AUDIT_LOGGER_NAME = "security.audit"


def ensure_security_audit_logging() -> logging.Logger:
    """Make the security audit logger actually emit at INFO.

    uvicorn attaches handlers to its own ``uvicorn.*`` loggers and leaves the root logger
    untouched, so a ``logger.info`` on ``security.audit`` reaches no handler at all and is
    discarded (an unconfigured root sits at WARNING and the last-resort handler only prints
    WARNING and above). Every audit event is emitted at INFO, so without this the audit trail
    — SECURITY_S0.5's code-execution events and SECURITY_S2B's login events alike — is written
    to nothing in production while appearing to work under pytest, where caplog supplies the
    handler.

    Only this logger is levelled, so turning the audit trail on does not also switch on INFO
    logging for every third-party library.
    """
    audit = logging.getLogger(AUDIT_LOGGER_NAME)
    audit.setLevel(logging.INFO)
    if not logging.getLogger().handlers and not audit.handlers:
        # Nothing downstream would print it, so the audit logger carries its own handler.
        # When the root IS configured (pytest's capture, or a deployment that calls
        # configure_logging) the record already propagates, and adding one here would print
        # every event twice.
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
        audit.addHandler(handler)
    return audit
