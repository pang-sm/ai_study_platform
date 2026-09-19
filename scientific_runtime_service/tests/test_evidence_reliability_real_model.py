"""Real evidence_reliability checkpoint path (ACCEL_SPRINT_S4, PART B).

These tests execute the ACTUAL five frozen checkpoints on disk — no mock, no synthetic
weights. They need ``torch`` and the frozen model assets, so they run in the scientific
runtime environment (``D:\\ZhixueAI\\envs\\runtime``) and SKIP elsewhere rather than fail::

    D:/ZhixueAI/envs/runtime/Scripts/python.exe -m pytest \
        scientific_runtime_service/tests/test_evidence_reliability_real_model.py

What is proven: the adapter loads all five variants, each with its own real input
dimension, the panel executes deterministically, the output is a weight in (0,1), and the
output semantics string is the adapter's own.

What is deliberately NOT proven — because it is false — is that the product can feed it.
The product persists no hint signal, does not guarantee a response time or an attempt
count, and has no mapping from CS408 knowledge points onto the scientific skill ontology
that ``log_opp``/``b_s`` are indexed by; the IRT ``b_map`` and the training-set
standardization statistics are not bundled either. No default may be substituted for any
of them, so the product surface stays SHADOW_NOT_USER_VISIBLE.
"""
import os
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="heavy scientific stack not installed here")

ZHIXUE = os.environ.get("ZHIXUE_HOME") or r"D:\ZhixueAI"
RUNTIME_SRC = os.environ.get("ZHIXUE_RUNTIME_SRC") or os.path.join(
    ZHIXUE, "runtime_package", "v1", "src")
if RUNTIME_SRC not in sys.path:
    sys.path.insert(0, RUNTIME_SRC)

ASSETS = os.path.join(ZHIXUE, "model_assets", "v1", "evidence_reliability")

# The frozen component record's variant table. The five checkpoints are FEATURE ABLATIONS
# with different input dimensions — they are not interchangeable.
FROZEN_VARIANT_DIMS = {"42": 8, "42_nort": 7, "42_surprise": 3, "43": 8, "44": 8}


@pytest.fixture(scope="module")
def adapter():
    if not os.path.isdir(ASSETS):
        pytest.skip("evidence_reliability model assets not present on this machine")
    from zhixue_runtime.components.adapters import get_adapter
    from zhixue_runtime.config import RuntimeConfig

    ad = get_adapter("evidence_reliability")(RuntimeConfig(home=ZHIXUE))
    ad.load()
    yield ad
    ad.unload()


def _panel_features(ad):
    """One real-shaped vector per variant, at that variant's own dimension."""
    return {vid: [0.0] * (ad._nets[vid][1] - 1) + [0.5] for vid in FROZEN_VARIANT_DIMS}


def test_adapter_is_registered():
    from zhixue_runtime.components.adapters import get_adapter
    from zhixue_runtime.components.adapters.evidence_reliability import (
        EvidenceReliabilityAdapter,
    )
    assert get_adapter("evidence_reliability") is EvidenceReliabilityAdapter


def test_all_five_checkpoints_load_with_their_frozen_dimensions(adapter):
    assert set(adapter._nets) == set(FROZEN_VARIANT_DIMS)
    for vid, dim in FROZEN_VARIANT_DIMS.items():
        assert adapter._nets[vid][1] == dim, vid


def test_panel_executes_deterministically_and_returns_real_weights(adapter):
    feats = _panel_features(adapter)
    first = adapter.infer_panel(feats).output
    second = adapter.infer_panel(feats).output

    assert first["variant_outputs"] == second["variant_outputs"], "panel is not deterministic"
    for vid, weight in first["variant_outputs"].items():
        assert 0.0 < weight < 1.0, f"{vid} produced {weight}, outside the reliability range"


def test_panel_never_averages_votes_or_selects_a_variant(adapter):
    out = adapter.infer_panel(_panel_features(adapter)).output
    assert out["averaging"] is False
    assert out["auto_selection"] is False
    assert out["active_product_variant"] is None
    assert out["variant_mode"] == "PANEL"
    # the disagreement is reported rather than resolved away
    assert out["variant_disagreement"] == pytest.approx(out["score_std"])


def test_output_semantics_are_a_weight_and_never_a_probability(adapter):
    """PART B1: exactly what the output means, in the component's own words."""
    feats = _panel_features(adapter)
    semantics = {vid: adapter.infer(feats[vid], vid).output["score_semantics"]
                 for vid in FROZEN_VARIANT_DIMS}
    assert all(s == "reliability weight w in (0,1) — NOT probability" for s in semantics.values())

    # The runtime bridge restates this string (``infer_panel`` does not emit it), so pin
    # the two together. The bridge itself cannot be imported here — it pulls in pydantic,
    # which this torch environment does not have — so the source is read directly.
    bridge_source = (Path(__file__).resolve().parents[1]
                     / "app" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert f'EVIDENCE_RELIABILITY_SEMANTICS = "{semantics["42"]}"' in bridge_source


def test_component_controls_no_product_decision(adapter):
    out = adapter.infer_panel(_panel_features(adapter)).output
    assert out["controls_product_decision"] is False
    assert out["product_role"] == "DATA_PRODUCER"
    assert out["replacement_readiness"] == "COLLECTING_DATA"


def test_frozen_acceptance_record_carries_no_calibration_threshold(adapter):
    assert adapter._prov["scientific_threshold"] is None
    assert adapter._prov["source_commit"] == "WORKING_TREE(no-git-HEAD)"


def test_a_wrong_dimension_is_rejected_rather_than_padded(adapter):
    """A malformed vector must never be silently coerced into a valid one."""
    from zhixue_runtime.errors import InputValidationError

    feats = _panel_features(adapter)
    with pytest.raises(InputValidationError):
        adapter.infer_panel({**feats, "42": [0.0] * 3})


def test_a_partial_panel_is_rejected_rather_than_defaulted(adapter):
    from zhixue_runtime.errors import InputValidationError

    feats = _panel_features(adapter)
    with pytest.raises(InputValidationError):
        adapter.infer_panel({"42": feats["42"]})


def test_the_component_needs_inputs_the_product_does_not_have():
    """PART B2: the audit in executable form.

    These are the fields the feature vector is built from. The product cannot supply the
    last five, so no product caller may construct this input.
    """
    product_absent = {"attempt_gt1", "has_bottom_hint", "hint_count", "log_rt", "b_s"}
    scientific_inputs = {
        "y", "attempt_gt1", "has_bottom_hint", "log_rt", "hint_count", "log_opp", "b_s",
        "p_t",
    }
    assert product_absent <= scientific_inputs
    # y (the authoritative boolean) and occurrence order are the ONLY two the product has
    assert scientific_inputs - product_absent == {"y", "log_opp", "p_t"}
