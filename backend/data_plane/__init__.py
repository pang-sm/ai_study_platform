"""Product Data Plane — Phase 2B1 foundation.

Persists immutable ITEM_LEVEL LearningEvents from course_practice submits (post-commit,
best-effort) and supports deterministic idempotent historical backfill.

No model inference is performed in this phase.
"""
