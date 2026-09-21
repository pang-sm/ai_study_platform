"""Ops layer (P6) — admin-only read contracts and the advanced-workflow kill switches.

Nothing here is a product capability and nothing here changes learner state: it is the
operational surface over facts the product already stores (``ai_requests``, ``ai_called``,
the canonical events) plus the feature-flag gate that can close a high-risk workflow without
a deploy.
"""
