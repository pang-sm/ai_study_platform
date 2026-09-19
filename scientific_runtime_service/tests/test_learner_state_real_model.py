"""Real learner_state model/checkpoint path (ACCEL_SPRINT_S3, PART D/O).

These tests execute the ACTUAL trained checkpoints on disk — no mock, no synthetic
weights. They need ``torch`` and the frozen model assets, so they run in the scientific
runtime environment (``D:\\ZhixueAI\\envs\\runtime``) and SKIP elsewhere rather than fail.
Run them with::

    D:/ZhixueAI/envs/runtime/Scripts/python.exe -m pytest \
        scientific_runtime_service/tests/test_learner_state_real_model.py

What is proven here is what PART D asks for: the adapter, the asset, the ontology sizes,
the output semantics, and the checkpoint provenance. What is deliberately NOT proven is
that the product can feed it — it cannot (see the domain-compatibility finding); the
product's Chinese CS408 concept space has no mapping onto these index ontologies.
"""
import hashlib
import json
import os
import sys

import pytest

torch = pytest.importorskip("torch", reason="heavy scientific stack not installed here")

ZHIXUE = os.environ.get("ZHIXUE_HOME") or r"D:\ZhixueAI"
RUNTIME_SRC = os.environ.get("ZHIXUE_RUNTIME_SRC") or os.path.join(
    ZHIXUE, "runtime_package", "v1", "src")
if RUNTIME_SRC not in sys.path:
    sys.path.insert(0, RUNTIME_SRC)

ASSETS = os.path.join(ZHIXUE, "model_assets", "v1", "learner_state")

# The frozen scientific fact this sprint must not blur.
FROZEN_ONTOLOGY_SIZES = {"DKT": 123, "SimpleKT": 123, "AKT": 123, "CGKT": 123, "CGKT_v2": 835}


@pytest.fixture(scope="module")
def adapter():
    if not os.path.isdir(ASSETS):
        pytest.skip("learner_state model assets not present on this machine")
    from zhixue_runtime.components.adapters import get_adapter
    from zhixue_runtime.config import RuntimeConfig

    return get_adapter("learner_state")(RuntimeConfig(home=ZHIXUE)).load()


def test_real_checkpoints_load_with_the_frozen_ontology_sizes(adapter):
    assert adapter.loaded is True
    assert adapter._num_skills == FROZEN_ONTOLOGY_SIZES


def test_every_checkpoint_sha256_matches_the_frozen_artifact(adapter):
    """Provenance is verified against the artifact, not asserted."""
    artifact_path = os.path.join(ASSETS, "artifact.json")
    if not os.path.exists(artifact_path):
        pytest.skip("artifact.json not present")
    artifact = json.load(open(artifact_path, encoding="utf-8"))
    assert artifact["source_commit"] == "06d4366"
    assert artifact["research_status"] == "frozen"

    mismatches = []
    for entry in artifact["files"]:
        path = os.path.join(ASSETS, entry["file"].replace("/", os.sep))
        if not os.path.exists(path):
            mismatches.append(f"missing: {entry['file']}")
            continue
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if digest != entry["sha256"]:
            mismatches.append(f"sha256: {entry['file']}")
    assert mismatches == [], mismatches


def test_real_inference_returns_finite_next_response_probabilities(adapter):
    q = [3, 3, 17, 17, 42]
    r_prev = [0, 1, 0, 1, 1]
    for family in FROZEN_ONTOLOGY_SIZES:
        out = adapter.infer(family, q, r_prev).output
        probs = out["next_response_probability"]
        assert len(probs) == len(q)
        assert all(0.0 <= p <= 1.0 for p in probs), (family, probs)
        assert out["num_skills"] == FROZEN_ONTOLOGY_SIZES[family]
        assert out["ontology"] in ("base", "junyi")


def test_real_inference_is_deterministic(adapter):
    a = adapter.infer("DKT", [1, 2, 3], [0, 1, 0]).output["next_response_probability"]
    b = adapter.infer("DKT", [1, 2, 3], [0, 1, 0]).output["next_response_probability"]
    assert a == b


def test_output_semantics_are_next_response_not_mastery(adapter):
    out = adapter.infer("SimpleKT", [1, 2], [0, 1]).output
    assert "next_response_probability" in out
    assert "P(correct)" in out["score_semantics"]
    assert "NOT mastery" in out["score_semantics"]
    for forbidden in ("mastery_probability", "mastery", "ability", "difficulty"):
        assert forbidden not in out


def test_panel_never_averages_or_auto_selects(adapter):
    """The variant panel reports variants side by side; it picks no winner."""
    out = adapter.infer_panel([1, 2, 3], [0, 1, 0]).output
    assert out["averaging"] is False
    assert out["auto_selection"] is False
    assert out["active_product_variant"] is None
    assert sorted(out["variant_outputs"]) == ["AKT", "CGKT", "CGKT_v2", "DKT", "SimpleKT"]


def test_index_outside_the_ontology_is_rejected_not_clamped(adapter):
    """A CS408-style arbitrary index must fail loudly rather than be silently accepted.

    This is the runtime half of the domain-compatibility finding: index 500 is not a
    concept, and the model must refuse it instead of inventing a meaning for it.
    """
    from zhixue_runtime.errors import InputValidationError

    with pytest.raises(InputValidationError):
        adapter.infer("DKT", [500], [0])
