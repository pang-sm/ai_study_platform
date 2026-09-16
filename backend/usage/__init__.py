"""Unified Subscription / Capability Permission / Usage Budget & Ledger (STEP 7B).

One effective subscription tier per user (Free / Standard / Advanced). Usage is tracked
as normalized credits (NOT tokens, NOT request count). Ledger is append-oriented and
idempotent. Cost engine keeps BOTH provider currency cost AND normalized credits.
"""
