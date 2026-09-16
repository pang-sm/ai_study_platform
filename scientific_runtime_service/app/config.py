"""Frozen scientific runtime service configuration.

No secrets, no filesystem paths. Production overrides binding via uvicorn/systemd, not
via secret-bearing config here.
"""
from __future__ import annotations

CONTRACT_VERSION = 1
RUNTIME_RELEASE_ID = "zhixue-runtime-v1-phase1gr-p1"
COMPONENT_ID = "student_twin"
SCIENTIFIC_SOURCE_CLASS = "ORIGINAL_ARCHIVE_VERIFIED"
# research-archive git commit for the student_twin scientific source (frozen provenance)
SCIENTIFIC_SOURCE_COMMIT = "a16efa27aac90d9c8d8d9ee703aefe5919f4839e"

HOST = "127.0.0.1"
PORT = 8101
