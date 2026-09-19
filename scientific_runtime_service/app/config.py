"""Frozen scientific runtime service configuration.

No secrets, no filesystem paths. Production overrides binding via uvicorn/systemd, not
via secret-bearing config here.
"""
from __future__ import annotations

CONTRACT_VERSION = 1
# The release id identifies the SCIENTIFIC source + engineering patch. Serving additional
# components over HTTP changes no scientific computation, no model asset and no
# student_twin numeric, so the id is NOT bumped: the same runtime release now answers more
# capabilities. The capability set is reported by /v1/capabilities.
RUNTIME_RELEASE_ID = "zhixue-runtime-v1-phase1gr-p1"
COMPONENT_ID = "student_twin"
# every component the service can serve. Adding one here is what makes it reachable; a
# component that is not listed has no product-facing surface at all.
COMPONENT_IDS = ("student_twin", "misconception_v2", "tutor_policy", "learner_state",
                 "evidence_reliability")
SCIENTIFIC_SOURCE_CLASS = "ORIGINAL_ARCHIVE_VERIFIED"
# research-archive git commit for the student_twin scientific source (frozen provenance)
SCIENTIFIC_SOURCE_COMMIT = "a16efa27aac90d9c8d8d9ee703aefe5919f4839e"
# frozen provenance for the two components added by the product bridge sprint
MISCONCEPTION_SOURCE_COMMIT = "565239a"
MISCONCEPTION_ONTOLOGY_DOMAIN = "Eedi misconception ontology (2587 entries, English)"
TUTOR_POLICY_SOURCE_COMMIT = "b716ae77e"
# APPENDED by ACCEL_SPRINT_S3. coursegraph_kt source commit, from the frozen component
# artifact (model_assets/v1/learner_state/artifact.json, research_status=frozen).
LEARNER_STATE_SOURCE_COMMIT = "06d4366"
# APPENDED by ACCEL_SPRINT_S4. evidence_reliability's scientific source was recovered from
# a working-tree snapshot with no git HEAD (the frozen component record says so), so its
# identity is the source class + the self-contained module, not a commit hash.
EVIDENCE_RELIABILITY_SOURCE_COMMIT = "WORKING_TREE(no-git-HEAD)"

HOST = "127.0.0.1"
PORT = 8101
