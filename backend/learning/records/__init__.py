"""Learning Records / Data Plane consolidation (STEP 7F).

    Product Facts → Trusted Event Producers → learning_events → Records read model
                                                              → Data Producer → Runtime

This package does NOT re-implement the STEP7A Data Plane. It adds the pieces that were
missing around it: a frozen event taxonomy, one authoritative owner per fact, a shared
envelope + validator, trusted producers for the remaining fact families, and a user-
facing read model over ``learning_events``.

Records are a PROJECTION of the event stream. There is no second record table.
"""
from . import envelope, service, taxonomy  # noqa: F401

__all__ = ["envelope", "service", "taxonomy"]
