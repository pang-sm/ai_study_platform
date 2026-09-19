"""Learning Spaces (domain layer).

Each space owns its domain content and pedagogy and COORDINATES the shared Learning
Core — it never re-implements it: no second practice service, no second wrong-answer
store, no second AI path, no provider SDK of its own.

Dependency direction is one-way:  Space → Learning Core → Platform Core.
"""
