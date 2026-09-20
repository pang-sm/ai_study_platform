"""ADMIN-ONLY scientific status: the capability registry plus the model-execution proof.

WHAT THIS IS FOR
----------------
Competition, demo and engineering proof. It answers the two questions an engineer or a
judge asks and an ordinary learner never does:

  * **What is the roadmap doing with each scientific capability?** — the frozen four-way
    category, so a research asset is never read as a backlog item and a shadow component
    is never read as a shipped one.
  * **Which self-developed models are real, and what proves it?** — one execution record
    per retained model: model family, the digests its provenance is pinned to, the runtime
    route that serves it, the test that actually executes it, and the blocker if it is not
    visible to a learner.

WHAT IT IS NOT
--------------
**This is NOT a learner page.** It is admin-gated at the route (see
``routers/scientific.py``), it carries no per-user field, and it takes no user parameter,
so it cannot be turned into a view of anybody's learning. Ordinary users reach the
capability summary through ``GET /exam/prep/scientific/capabilities``, which is a
different, user-safe payload.

DELIBERATELY ABSENT, AND WHY
----------------------------
    raw prompts          no prompt text exists in this payload at all
    learner data         no username, id, event, answer or grade; nothing per-user
    filesystem paths     model assets live outside the repository and the configured
                         runtime base URL is deployment configuration — neither is
                         exposed. A runtime is named by its LOGICAL route
                         (``POST /v1/inference/<component>``) and by whether it answers,
                         never by where it is installed or which host serves it
    secrets              no key, token, DSN or credential is read by this module

The digest values that ARE exposed are sha256 of published research source and of model
artifacts. A digest is the standard way to prove an artifact is the one you think it is;
it reveals nothing about where the artifact lives.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import capabilities, evidence_reliability, learner_state, misconception, tutor_policy

STATUS_SCHEMA_VERSION = "science-status-v1"

# The mode a component is in when the product CANNOT execute it at all, as opposed to
# choosing not to show it. Kept distinct so "not provisioned here" never reads as
# "scientifically rejected".
NOT_PROVISIONED = "RUNTIME_COMPONENT_NOT_PROVISIONED"

LEARNED = True
NOT_LEARNED = False


def _model(*, component, model_family, learned_model, runtime_path, product_mode, category,
           category_reason, blocker, user_visible, real_model_test=None,
           artifact_digests=None, provenance=None, semantics=None, notes=None) -> dict:
    """One retained model's execution record. Every field is a FACT already recorded by the
    module that owns the component — nothing here is restated from memory or computed."""
    record = {
        "component": component,
        "model_family": model_family,
        # False for a component that is a program rather than a fitted model. Reported
        # rather than omitted: a reader must be able to see that the ONE user-visible
        # scientific capability carries no checkpoint at all.
        "learned_model": learned_model,
        "runtime_endpoint": f"POST {runtime_path}",
        "product_mode": product_mode,
        "category": category,
        "category_reason": category_reason,
        "user_visible": user_visible,
        "blocker": blocker,
        "artifact_digests": dict(artifact_digests or {}),
        "real_model_test": real_model_test,
        "provenance": provenance,
        "semantics": semantics,
    }
    if notes:
        record["notes"] = list(notes)
    return record


def model_execution_proof() -> list[dict]:
    """One record per retained self-developed model, in registry order.

    ``checkpoint_hashes`` is populated only where the product's own source pins them. Where
    the artifact lives in a deployment-time bundle, the digest is verified against that
    bundle's manifest by the real-model test instead, and this record says so rather than
    leaving the field ambiguously empty.
    """
    return [
        _model(
            component="student_twin",
            model_family="DETERMINISTIC_RULE_BASED_STATE_ENGINE",
            learned_model=NOT_LEARNED,
            runtime_path="/v1/inference/student-twin",
            product_mode=capabilities.metadata.MODE_PREVIEW,
            category=capabilities.CATEGORY_USER_VISIBLE,
            category_reason=None,
            blocker=None,
            user_visible=True,
            real_model_test=None,
            provenance={"source_class": "ORIGINAL_ARCHIVE_VERIFIED"},
            semantics=("deterministic replay of the caller's own practice facts into an "
                       "experimental learning-state view — NOT a neural model, NOT a "
                       "mastery score, NOT a prediction"),
            notes=("the ONE user-visible scientific capability, and it has no checkpoint: "
                   "there is nothing trained behind it to be wrong about"),
        ),
        _model(
            component="learner_state",
            model_family="KNOWLEDGE_TRACING_PANEL",
            learned_model=LEARNED,
            runtime_path=learner_state.RUNTIME_PATH,
            product_mode=capabilities.metadata.MODE_SHADOW_NOT_USER_VISIBLE,
            category=capabilities.CATEGORY_RESEARCH_ONLY,
            category_reason=capabilities.REASON_ONTOLOGY_MISMATCH,
            blocker=learner_state.BLOCKER_ONTOLOGY,
            user_visible=False,
            real_model_test=("scientific_runtime_service/tests/"
                             "test_learner_state_real_model.py"),
            artifact_digests={},
            provenance={
                "families": list(learner_state.SCIENTIFIC_FAMILIES),
                "source_commit": learner_state.SCIENTIFIC_SOURCE_COMMIT,
                "ontology_index_sizes": dict(learner_state.SCIENTIFIC_ONTOLOGIES),
                "digest_verification": ("per-checkpoint sha256 is verified against the "
                                        "deployed artifact manifest by the real-model "
                                        "test; the manifest is deployment-side and its "
                                        "location is deliberately not exposed here"),
            },
            semantics=("next-response P(correct) — NOT mastery probability, NOT exam-pass "
                       "probability, NOT ability"),
            notes=("the panel never averages or auto-selects a family: every family is "
                   "reported separately, by design"),
        ),
        _model(
            component="evidence_reliability",
            model_family="RELIABILITY_NET_VARIANT_PANEL",
            learned_model=LEARNED,
            runtime_path=evidence_reliability.RUNTIME_PATH,
            product_mode=evidence_reliability.PRODUCT_MODE,
            category=capabilities.CATEGORY_SHADOW_COLLECTING_DATA,
            category_reason=capabilities.REASON_DATA_GATE_PENDING,
            blocker=evidence_reliability.BLOCKER_ONTOLOGY,
            user_visible=False,
            real_model_test=("scientific_runtime_service/tests/"
                             "test_evidence_reliability_real_model.py"),
            artifact_digests=dict(evidence_reliability.SCIENTIFIC_SOURCE_SHA256),
            provenance={
                "checkpoint_variants": dict(evidence_reliability.SCIENTIFIC_VARIANTS),
                "variant_mode": evidence_reliability.VARIANT_MODE,
                "active_product_variant": evidence_reliability.ACTIVE_PRODUCT_VARIANT,
                "source_class": evidence_reliability.SCIENTIFIC_SOURCE_CLASS,
                "scientific_threshold": evidence_reliability.SCIENTIFIC_THRESHOLD,
                "scaler_recovery": bool(evidence_reliability.SCALER_RECOVERY_EVIDENCE),
            },
            semantics=("a reliability weight w in (0,1) for ONE observation — NOT the "
                       "probability the response is correct and NOT a confidence"),
            notes=("the scaler gate is CLOSED by measurement; the component still does not "
                   "show because the INPUT gate is independently open — recovering a "
                   "preprocessing step was never a promotion criterion"),
        ),
        _model(
            component="misconception_v2",
            model_family="DUAL_ENCODER_RETRIEVAL_BGE_M3_FAISS",
            learned_model=LEARNED,
            runtime_path=misconception.RUNTIME_PATH,
            product_mode=misconception.PRODUCT_MODE,
            category=capabilities.CATEGORY_RESEARCH_ONLY,
            category_reason=capabilities.REASON_ONTOLOGY_MISMATCH,
            # Normalised to a stable code: the module's own constant is a paragraph, and a
            # status field that holds a paragraph cannot be asserted on or compared.
            blocker=capabilities.REASON_ONTOLOGY_MISMATCH,
            user_visible=False,
            real_model_test=None,
            artifact_digests={},
            provenance={"ontology": "Eedi misconception set (English)"},
            semantics=("a retrieval SIMILARITY over a candidate ontology — NOT a "
                       "probability, NOT a confidence, NOT a diagnosis"),
            notes=("two independent blockers, not one: the ontology mismatch is the "
                   "scientific one, and the component is additionally not provisioned in "
                   "the deployed runtime. The bridge is wired and answers, and nothing it "
                   "returns is shown or written.",
                   misconception.BLOCKER_ONTOLOGY),
        ),
        _model(
            component="tutor_policy",
            model_family="ENCODER_4WAY_ACTION_CLASSIFIER_BGE_M3",
            learned_model=LEARNED,
            runtime_path=tutor_policy.RUNTIME_PATH,
            product_mode=tutor_policy.PRODUCT_MODE,
            category=capabilities.CATEGORY_SHADOW_COLLECTING_DATA,
            category_reason=capabilities.REASON_MISSING_TURN_STATE,
            blocker="MISSING_TRUTHFUL_TURN_STATE_FIELDS",
            user_visible=False,
            real_model_test=None,
            artifact_digests={},
            provenance={"action_ontology": list(tutor_policy.ACTION_ONTOLOGY)},
            semantics=("a suggested pedagogical action over focus/generic/probing/"
                       "telling; it controls no tutor response and no caller consumes it"),
            notes=("the road to this component runs through DATA, not code: the product "
                   "owns no ledger of pedagogical actions taken per turn, so the prior-"
                   "action and confusion inputs would have to be invented. Only fields the "
                   "product actually records are collected."),
        ),
    ]


def category_status() -> dict:
    """The frozen four-way view: which capability is in which category, and why.

    ``by_category`` spans the thirteen AND the product-native entries; ``of_the_thirteen``
    is the same count restricted to the SSOT §36 set, so the two
    scopes cannot be silently compared against each other.
    """
    summary = capabilities.summary()
    native = summary["product_native_capabilities"]
    return {
        "categories": list(capabilities.CATEGORIES),
        "user_visible": [e["component"] for e in summary["components"] if e["user_visible"]],
        "by_category": {category: sorted(
            [e["component"] for e in summary["components"] if e["category"] == category]
            + [e["component"] for e in native if e["category"] == category])
            for category in capabilities.CATEGORIES},
        "of_the_thirteen": {category: sorted(
            e["component"] for e in summary["components"] if e["category"] == category)
            for category in capabilities.CATEGORIES},
        "product_native": sorted(e["component"] for e in native),
    }


def diagnostics(*, runtime_reachable: bool | None = None) -> dict:
    """The full admin payload. Pure and read-only; no runtime call unless the caller asks.

    ``runtime_reachable`` is passed IN rather than probed here so this function stays a
    pure composition: a diagnostic that reaches out to a service while being called is a
    diagnostic that can hang while being read.
    """
    summary = capabilities.summary()
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audience": "ADMIN_ONLY",
        "not_a_learner_page": True,
        "ordinary_users_see": sorted(
            e["component"] for e in summary["components"] if e["user_visible"]),
        "category_status": category_status(),
        "capability_totals": summary["totals"],
        "capabilities": summary["components"],
        "product_native_capabilities": summary["product_native_capabilities"],
        "models": model_execution_proof(),
        "runtime": {
            "reachable": runtime_reachable,
            "note": ("None means NOT PROBED, which is a different answer from False. The "
                     "configured base URL is deployment configuration and is not exposed "
                     "here; a component is named by its logical route."),
        },
        "terminology": {
            "category": summary["terminology"]["category"],
            "category_meaning": summary["category_meaning"],
            "learned_model": ("True only for a component with fitted parameters. A "
                              "deterministic program is reported as False rather than "
                              "omitted"),
            "ordinary_users_see": ("the only components an ordinary learner may be shown. "
                                   "Everything else in this payload is internal status"),
        },
    }
