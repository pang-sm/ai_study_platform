"""evidence_reliability product integration (ACCEL_SPRINT_S4) — a GATED capability report.

WHAT evidence_reliability IS
----------------------------
A self-supervised RELIABILITY SCORER. An interaction feature vector
``x = (7 static features, p_t)`` is mapped by a small MLP (``ReliabilityNet``,
8->16->16->1, sigmoid) to a weight ``w in (0,1)``. The scorer is trained so that a causal
learner-state update ``theta <- theta + alpha * w * (y - p)`` down-weights unreliable
observations (guesses and slips) and lowers future-response LogLoss. No guess/slip label
is ever used — the objective is self-supervised.

``w`` is a RELIABILITY WEIGHT. It is NOT the probability the response is correct, NOT a
confidence, NOT a judgement about the learner, and NOT a mastery score. Those are different
quantities and the field names here are part of the semantic gate.

The component ships as a VARIANT PANEL: five frozen checkpoints (``42``, ``42_nort``,
``42_surprise``, ``43``, ``44``) that are FEATURE ABLATIONS with different input
dimensions (8 / 7 / 3 / 8 / 8). The adapter loads all five and never averages, votes, or
auto-selects a winner; ``active_product_variant`` is None.

WHY IT PRODUCES NO NUMBER
-------------------------
The model is real and it executes — verified against the real checkpoints, panel latency
~2 ms, deterministic across runs. What does not exist is an honest INPUT.

Its feature vector is built, per interaction, from:

  static   y, attempt_gt1, has_bottom_hint, log_rt, hint_count,
           log1p(opportunity), b_s (IRT skill difficulty)
  dynamic  p_t = sigmoid(theta_t)   -- the component's own running learner-state prediction

Every one of the following is a REAL, independent reason this product cannot construct
that vector, and none of them may be worked around by supplying a default:

  * ``hint_count`` / ``has_bottom_hint`` — the product persists no hint signal at all. The
    canonical pipeline writes ``hints = None`` unconditionally.
  * ``log_rt`` — ``response_time_ms`` exists as a nullable column, is never set by the
    historical backfill, and is not guaranteed on live rows. Inventing a latency is
    forbidden.
  * ``attempt_gt1`` — ``attempt_no`` is likewise nullable and not guaranteed. An attempt
    count must never be fabricated.
  * ``log_opp`` and ``b_s`` are indexed by ``skill_id`` in the SCIENTIFIC ontology. That is
    the same ontology gap that blocks ``learner_state``: the product has Chinese CS408
    knowledge points and no mapping to the scientific skill space.
  * ``b_s`` additionally needs the IRT ``b_map`` — recoverable from the research archive,
    but keyed by the scientific skill space, so it is not a product input.
  * ``p_t`` is the running prediction of the SAME per-(user, skill) theta recurrence, so it
    inherits every blocker above.
  * The four continuous features are z-scored with the TRAINING set's mean/std. These WERE
    a blocker (S4/S5) and no longer are: S7 re-derived and VERIFIED them against every
    frozen per-row output and recorded them in ``SCALER_STANDARDIZATION_PARAMS``. Scaling
    was never the binding constraint — the columns being scaled still have no source.

So ``EVIDENCE_RELIABILITY_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE``, and the reason is now
narrower than it was: the SCALER gate is closed and the INPUT-COMPATIBILITY gate is not.
``production_mode()`` reads both, so the closed gate cannot silently open the surface.

It writes nothing: no knowledge status, no mastery, no wrong-answer state, no plan, no
grade, no learner fact of any kind. ``controls_product_decision`` is permanently False.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session as DbSession

from . import metadata
from .client import ScientificClient, get_client

logger = logging.getLogger("science.evidence_reliability")

COMPONENT = "evidence_reliability"
CONTRACT_VERSION = 1
RUNTIME_PATH = "/v1/inference/evidence-reliability"

# The product surface is closed until an honest input exists. Same convention as
# ``science.misconception`` / ``science.tutor_policy``: the mode is a module constant so
# the capability summary and the response can never disagree.
PRODUCT_MODE = metadata.MODE_SHADOW_NOT_USER_VISIBLE

# Frozen scientific identity (same convention as the other components: recorded as a
# contract fact, never imported). The source was recovered from a working-tree snapshot
# with no git HEAD, which is what the frozen component record itself states.
SCIENTIFIC_SOURCE_CLASS = "ORIGINAL_ARCHIVE_VERIFIED"
SCIENTIFIC_SOURCE_COMMIT = "WORKING_TREE(no-git-HEAD)"

# variant id -> input dimension of that checkpoint, from the frozen component record.
SCIENTIFIC_VARIANTS = {"42": 8, "42_nort": 7, "42_surprise": 3, "43": 8, "44": 8}
VARIANT_MODE = "PANEL"
ACTIVE_PRODUCT_VARIANT = None
REPLACEMENT_READINESS = "COLLECTING_DATA"

# The frozen acceptance record carries scientific_threshold = null: no calibration or
# validity threshold was ever established for this component.
SCIENTIFIC_THRESHOLD = None

# ================================================================ PART C (S5) — THE EXACT
# INPUT CONTRACT, READ OFF THE FROZEN TRAINING SOURCE
#
# Every fact below is transcribed from the recovered research source, NOT from memory and
# NOT from a summary of it. The governing file is the model module the adapter extracts
# (``ReliabilityNet`` + ``build_sequences`` + ``unroll_batch``) and the training driver
# that calls it. Their sha256 are recorded in ``SCIENTIFIC_SOURCE_SHA256`` so the
# transcription can be re-verified against the exact bytes it was read from.
#
# THE VECTOR. One interaction -> x. The static block is laid out by the source's own
# ``STATIC_ORDER = BIN_FEATS + CONT_FEATS``; the dynamic ``p_t`` is concatenated LAST by
# ``unroll_batch`` (``torch.cat([feat[:, t, :], p.unsqueeze(1)], dim=1)``). So an 8-wide
# variant reads:
#
#     x = [y, attempt_gt1, has_bottom_hint, z(log_rt), z(hint_count), z(log_opp),
#          z(b_s), p_t]
#
# The three binary features are RAW 0/1 and are NOT standardized; only ``CONT_FEATS``
# (``log_rt``, ``hint_count``, ``log_opp``, ``b_s``) are z-scored. Getting that split
# wrong silently changes every subsequent number.
BIN_FEATURES = ("y", "attempt_gt1", "has_bottom_hint")
CONT_FEATURES = ("log_rt", "hint_count", "log_opp", "b_s")
STATIC_ORDER = BIN_FEATURES + CONT_FEATURES
DYNAMIC_FEATURES = ("p_t",)

# The full 8-wide vector, in position order. Variant input widths are STRICT PREFIXES of
# this layout (an ablation drops columns, it never reorders them).
FEATURE_VECTOR = STATIC_ORDER + DYNAMIC_FEATURES

FEATURE_SCHEMA = (
    {"index": 0, "name": "y", "block": "BIN", "dtype": "0/1",
     "semantics": "authoritative binary correctness of THIS interaction",
     "raw_unit": "boolean",
     "transform": "none (raw 0/1)",
     "source_expression": "c['correct'].astype('int8')"},
    {"index": 1, "name": "attempt_gt1", "block": "BIN", "dtype": "0/1",
     "semantics": "whether this response was a REPEAT attempt on the same problem",
     "raw_unit": "boolean",
     "transform": "none (raw 0/1)",
     "source_expression": "(df['attempt_count'] > 1).astype('int8')"},
    {"index": 2, "name": "has_bottom_hint", "block": "BIN", "dtype": "0/1",
     "semantics": "whether the bottom-out hint was used on this interaction",
     "raw_unit": "boolean",
     "transform": "none (raw 0/1)",
     "source_expression": "(df['bottom_hint'] == 1).astype('int8') — NA/NaN != 1 -> 0"},
    {"index": 3, "name": "log_rt", "block": "CONT", "dtype": "float",
     "semantics": "log-scaled response time to the FIRST response of the interaction",
     "raw_unit": "log1p(milliseconds); the milliseconds are the ASSISTments field "
                 "ms_first_response",
     "transform": "z = (log1p(max(ms, 0)) - mean[log_rt]) / std[log_rt]",
     "source_expression": "np.log1p(df['ms_first_response'].clip(lower=0))"},
    {"index": 4, "name": "hint_count", "block": "CONT", "dtype": "float",
     "semantics": "number of hint requests on this interaction",
     "raw_unit": "count, integer",
     "transform": "z = (hint_count - mean[hint_count]) / std[hint_count]",
     "source_expression": "df['hint_count'] (int32)"},
    {"index": 5, "name": "log_opp", "block": "CONT", "dtype": "float",
     "semantics": "log-scaled opportunity count for THIS learner on THIS skill, i.e. how "
                  "many times the learner has met this skill before",
     "raw_unit": "log1p(count); the count is the ASSISTments field `opportunity`, indexed "
                 "by the SCIENTIFIC skill_id space",
     "transform": "z = (log1p(opportunity) - mean[log_opp]) / std[log_opp]",
     "source_expression": "np.log1p(c['opportunity'])"},
    {"index": 6, "name": "b_s", "block": "CONT", "dtype": "float",
     "semantics": "IRT 1PL skill difficulty of the interaction's skill",
     "raw_unit": "logit-scale IRT b, keyed by the SCIENTIFIC skill_id space",
     "transform": "VARIANT-DEPENDENT — see B_S_PER_VARIANT. Variant 42 z-scores it "
                  "(z = (b_s - mean[b_s]) / std[b_s]); the other four feed the mapped "
                  "value RAW. Both were measured, not read off one source revision.",
     "source_expression": "c['skill_id'].map(b_map).fillna(0.0), b_map = "
                          "irt_skill_params.json['b_1pl']"},
    {"index": 7, "name": "p_t", "block": "DYN", "dtype": "float",
     "semantics": "the component's OWN running learner-state prediction at this step",
     "raw_unit": "probability in (0,1)",
     "transform": "none — already in (0,1); it is NOT z-scored",
     "source_expression": "sigmoid(theta_t) of the per-(user, skill) recurrence "
                          "theta <- theta + alpha * w * (y - p)"},
)

# Missing-value handling, exactly as the frozen pipeline does it. Nothing else is filled:
# every other absent value would propagate as NaN and the adapter rejects a non-finite
# vector rather than imputing one.
MISSING_VALUE_POLICY = {
    "b_s": "skill missing from b_map -> 0.0 BEFORE standardization (source: fillna(0.0))",
    "has_bottom_hint": "bottom_hint NA/NaN -> 0 (a NaN is not equal to 1)",
    "log_rt": "ms_first_response is clipped to >= 0 before log1p; no other imputation",
    "all_others": "no fill — a missing value is left missing, never imputed",
}

# The standardization the checkpoints were trained under. This is NOT a hyper-parameter
# that may be re-chosen; it is part of the frozen model and a caller that does not hold
# these exact numbers cannot construct a valid input.
STANDARDIZATION = {
    "applies_to": list(CONT_FEATURES),
    "not_applied_to": list(BIN_FEATURES + DYNAMIC_FEATURES),
    "formula": "z = (value - mean) / std",
    "mean_source": "the TRAIN-SPLIT rows of the seed's cohort (train users only)",
    "std_source": "same rows; sample std (ddof=1), with a `or 1.0` guard when std == 0",
    "computed_by": "build_sequences(...) on first call, then reused unchanged for val/test",
    "bundled_with_checkpoints": False,
    "recorded_in_product_module": True,
    "recorded_as": "SCALER_STANDARDIZATION_PARAMS (per seed, with per-variant b_s mode)",
    "verification": ("reproduces every frozen per-row output of all five checkpoints to "
                     "1.788e-07 (float32) across 188,262 rows — ACCEL_SPRINT_S7"),
    "b_s_caveat": ("b_s is z-scored for variant 42 and RAW for the other four; see "
                   "B_S_PER_VARIANT. One table, two modes — a caller must pick per variant"),
}

# ---------------------------------------------------------------- B_S_PER_VARIANT
#
# THE ONE BRANCH THAT DIFFERS BETWEEN THE ARCHIVED SOURCE AND THE FROZEN RUNS.
#
# The archived ``build_sequences`` sends ``b_s`` down the ``if c == "b_s"`` branch, which
# emits the mapped value RAW; only the ``else`` branch z-scores. Measured against the five
# frozen per-row experiment outputs (188,262 prediction rows), four of the five checkpoints
# reproduce EXACTLY under the archived branch, and exactly one — the base ``42`` run — does
# not: it reproduces only when ``b_s`` is z-scored instead. So the base run predates that
# branch and the branch was added before the other four were trained. Both facts are
# measurements on frozen bytes, not readings of a single source revision.
#
# The base run's fitted (mean, std) is NOT a free fit that happened to land: it equals the
# independently re-derived train-row statistics of ``b_s`` to seven significant digits
# (fitted -0.536745874 / 0.653580144 against re-derived -0.536745877 / 0.653580218). A
# curve fit that reproduces a number nobody constrained would not agree with the pipeline's
# own rule, and this one does.
B_S_MODE_ZSCORED = "ZSCORED"
B_S_MODE_RAW = "RAW"
B_S_PER_VARIANT = {
    "42": B_S_MODE_ZSCORED,
    "42_nort": B_S_MODE_RAW,
    "42_surprise": B_S_MODE_RAW,
    "43": B_S_MODE_RAW,
    "44": B_S_MODE_RAW,
}

# What the source does BEFORE features are built, transcribed so the split and the
# sequence construction can never be re-invented downstream.
TRAINING_PIPELINE = {
    "dataset": "ASSISTments 2009-2010 skill_builder_data_corrected.csv",
    "cohort_filter": "original == 1 (main problems only) AND skill_id not null",
    "split": "user-disjoint 70/15/15 over np.sort(unique(user_id)) using "
             "np.random.default_rng(seed).permutation(n); seeds 42 / 43 / 44",
    "sequence_grouping": "per (skill_id, user_id), ordered by order_id, truncated to the "
                         "first T_max = 200 interactions; theta resets to 0 per sequence",
    "alpha": "tuned on VAL for the equal-weight BASE model over "
             "0.2,0.5,0.8,1.0,1.5,2.0,3.0; the chosen value is stored in "
             "results/comparison_{seed}.json and is NOT bundled with the checkpoints",
}

# sha256 of the exact bytes each fact above was read from. Recomputing these and finding a
# different digest means the transcription no longer describes the source on disk.
SCIENTIFIC_SOURCE_SHA256 = {
    "evidence_reliability/evidence_reliability.py":
        "4f8fdbcc3997e58501901fa234fbde0914bb31aa99da2e71d821d663128ae8c3",
    "evidence_reliability/run_experiment.py":
        "f60762fe32b9a96240d1c5ef2c4340aec430057d51edb989c2a0b396e2ad8c31",
    "evidence_reliability/build_splits.py":
        "9c68c3c7aaf877e4fbde034e3b2646163021bc7d26b1d3a911bca5d9aeebd439",
    "evidence_reliability/irt.py":
        "2710df26930f89208df9f464a1e5f4ba951d6359589fd40477653412d99d2b75",
}

# ---------------------------------------------------------------- PART C — PRODUCT
# COMPATIBILITY, per feature. This is the answer to "can this product honestly produce
# this value?", and it is a DIFFERENT question from "does the column exist".
AVAILABLE_NOW = "AVAILABLE_NOW"
CAN_BE_COLLECTED_FACTUALLY = "CAN_BE_COLLECTED_FACTUALLY"
NOT_AVAILABLE = "NOT_AVAILABLE"
SEMANTICALLY_INCOMPATIBLE = "SEMANTICALLY_INCOMPATIBLE"

FEATURE_AVAILABILITY = (
    {"index": 0, "name": "y", "product_status": AVAILABLE_NOW,
     "product_source": "LearningEvent.correct, under the frozen canonical eligibility "
                       "rule (data_plane.eligibility)",
     "why": "the product already holds a real authoritative boolean for a CS408 practice "
            "interaction; this is one of the two features that are genuinely present"},
    {"index": 1, "name": "attempt_gt1", "product_status": CAN_BE_COLLECTED_FACTUALLY,
     "product_source": "a per-(user, question) attempt index recorded at the canonical "
                       "attempt boundary",
     "why": "the product records attempts, but NOT with the source's semantics: the "
            "ASSISTments field counts re-attempts WITHIN one problem presentation, while "
            "the product's existing attempt_no on past papers is a PAPER-SITTING number. "
            "A value may only be supplied once a per-(user,question) attempt index with "
            "the matching semantics exists; the two must not be conflated"},
    {"index": 2, "name": "has_bottom_hint", "product_status": NOT_AVAILABLE,
     "product_source": None,
     "why": "the product has NO hint system on any CS408 practice surface, so no hint "
            "interaction can be recorded. This is NOT the same as hints == 0: the source's "
            "`bottom_hint == 1` is 'used the bottom-out hint', and its absence in "
            "ASSISTments means the learner never asked. A surface with no hint mechanism "
            "at all is a DIFFERENT domain, and writing 0 there would assert a fact about "
            "learners that was never observed. It therefore stays missing"},
    {"index": 3, "name": "log_rt", "product_status": CAN_BE_COLLECTED_FACTUALLY,
     "product_source": "a factual per-item duration captured between a defined serve "
                       "boundary and a defined submit boundary",
     "why": "the raw unit (milliseconds since first response) has a product counterpart, "
            "but only a duration with DEFINED boundaries qualifies. The product must not "
            "reconstruct one from created_at/submitted_at unless those two timestamps "
            "actually bracket active answering, and must not infer it from a session "
            "span. Until such a duration is collected the value is missing — NOT zero"},
    {"index": 4, "name": "hint_count", "product_status": NOT_AVAILABLE,
     "product_source": None,
     "why": "same as has_bottom_hint: no hint interaction exists to count, and a "
            "fabricated 0 would be a claim the product cannot support"},
    {"index": 5, "name": "log_opp", "product_status": SEMANTICALLY_INCOMPATIBLE,
     "product_source": None,
     "why": "`opportunity` is a count in the SCIENTIFIC skill_id space (ASSISTments "
            "skills), and its standardized value is measured against the ASSISTments "
            "training distribution. A CS408-native per-concept opportunity count is a "
            "different quantity on a different support; passing it through this feature's "
            "frozen mean/std would feed the model a number that does not mean what the "
            "model was trained to read"},
    {"index": 6, "name": "b_s", "product_status": SEMANTICALLY_INCOMPATIBLE,
     "product_source": None,
     "why": "IRT 1PL skill difficulty keyed by the scientific skill_id space. The IRT "
            "b_map is itself NOT bundled, and the product's CS408 knowledge points have "
            "no mapping onto that space. There is nothing to look up, and nothing that "
            "could stand in for a lookup"},
    {"index": 7, "name": "p_t", "product_status": SEMANTICALLY_INCOMPATIBLE,
     "product_source": None,
     "why": "p_t is sigmoid(theta) of the component's OWN per-(user, skill) theta "
            "recurrence, so it inherits the skill ontology of log_opp/b_s AND needs the "
            "fitted alpha, which is not bundled. It is not an independent feature that "
            "could be sourced elsewhere"},
)

# A single boolean summary of the table above, so no reader has to re-derive it.
PRODUCT_FEATURE_COMPATIBILITY = "INCOMPATIBLE"
INCOMPATIBLE_FEATURES = tuple(f["name"] for f in FEATURE_AVAILABILITY
                              if f["product_status"] != AVAILABLE_NOW)

# ---------------------------------------------------------------- PART A — THE SCALER
# GATE, as an executable record rather than prose.
#
# ACCEPTABLE recovery is one of:
#   A. the fitted mean/std (or a serialized scaler) is found, OR
#   B. the frozen training dataset + exact split + exact preprocessing pipeline are all
#      present, so the scaler can be RE-DERIVED deterministically from frozen bytes.
# Everything else is forbidden, including fitting on product users, on a test batch, on
# the inference batch, guessing mean=0/std=1, borrowing stats from another experiment, or
# trying to invert them out of the checkpoint weights.
SCALER_GATE_ACCEPTED_METHODS = ("FOUND_FITTED_ARTIFACT", "RECONSTRUCTED_FROM_FROZEN_DATA")
SCALER_GATE_FORBIDDEN_METHODS = (
    "FIT_ON_PRODUCT_USERS", "FIT_ON_TEST_SPLIT", "FIT_ON_INFERENCE_BATCH",
    "ASSUME_STANDARD_NORMAL", "COPY_FROM_OTHER_EXPERIMENT", "DERIVE_FROM_CHECKPOINT",
)

# What the recovery needs that the product does NOT hold. Present so the gate can be
# re-evaluated the moment the artifacts appear, without redoing the audit.
SCALER_RECOVERY_REQUIREMENTS = (
    "mean[log_rt], mean[hint_count], mean[log_opp], mean[b_s] and the matching std "
    "values — the four (mean, std) pairs the checkpoint consumes",
    "OR, to re-derive them: data/splits/cohort.parquet — built by build_splits.load_cohort "
    "from the raw ASSISTments CSV (original == 1, skill_id not null)",
    "OR, to re-derive them: data/splits/split_{42,43,44}.parquet — the user-disjoint "
    "partitions; the scaler is computed over the TRAIN users of the seed that trained the "
    "variant",
    "OR, to re-derive them: results/irt_skill_params.json — supplies b_1pl, which b_s is "
    "built from and which is itself one of the four standardized columns",
)

# The gate itself. SHADOW_NOT_USER_VISIBLE is the only value this constant may take until
# an artifact satisfying ACCEPTED_METHODS is present AND its digest is recorded here.
#
# ACCEL_SPRINT_S7 closed this gate. See SCALER_RECOVERY_EVIDENCE for the measurement and
# SCALER_STANDARDIZATION_PARAMS for the recovered numbers.
SCALER_RECOVERY_METHOD = "RECONSTRUCTED_FROM_FROZEN_DATA"

# The recovered standardizer, per training seed. These are the four (mean, std) pairs the
# checkpoints consume, re-derived from the frozen cohort + split by the pipeline's own rule
# and then PROVEN against the frozen per-row outputs.
#
# They live here as the RECOVERED ARTIFACT rather than as prose because a caller that holds
# them can construct a valid input vector; a caller that does not, cannot. Recovering them
# closes the scaler gate — it does NOT close the input gate, because three of the four
# columns they scale are still indexed by the scientific skill ontology. See
# PRODUCT_FEATURE_COMPATIBILITY.
SCALER_STANDARDIZATION_PARAMS = {
    "42": {"mean": {"log_rt": 9.996226348912442, "hint_count": 0.4309670328474501,
                    "log_opp": 2.0489708966992666, "b_s": -0.5367458774637446},
           "std": {"log_rt": 1.2743737786514842, "hint_count": 1.161659884396357,
                   "log_opp": 0.9819057002510351, "b_s": 0.6535802182457324}},
    "43": {"mean": {"log_rt": 9.977563363223293, "hint_count": 0.436419793295119,
                    "log_opp": 2.0525352185998123, "b_s": -0.5289049056700561},
           "std": {"log_rt": 1.2736077917340578, "hint_count": 1.1711556374829706,
                   "log_opp": 0.9817996256178723, "b_s": 0.6558011755760538}},
    "44": {"mean": {"log_rt": 9.983235640757911, "hint_count": 0.44867742836640906,
                    "log_opp": 2.0468744520757203, "b_s": -0.5299756433775145},
           "std": {"log_rt": 1.2769397209811848, "hint_count": 1.1858596266620325,
                   "log_opp": 0.9640768130379006, "b_s": 0.6558903577230928}},
}
# The seed-42 variants (42_nort, 42_surprise) share the 42 split, so they share its
# statistics; the seed is what selects a row of the table, not the variant name.
SCALER_STANDARDIZATION_PARAMS_BY_VARIANT = {
    "42": "42", "42_nort": "42", "42_surprise": "42", "43": "43", "44": "44",
}

# WHAT WAS ACTUALLY MEASURED, so the next attempt starts from facts rather than from prose.
#
# S5 attempted the same reconstruction and reported REPRODUCTION_FAILED. That verdict was
# WRONG, and S7 established why: S5's forward pass followed the archived source's
# ``if c == "b_s"`` branch, which emits b_s RAW, for a checkpoint (the base 42 run) that
# was trained with it Z-SCORED. The standardizer S5 derived was already correct; only the
# verification of it was mis-modelled.
#
# S7 re-derived the transform from the frozen bytes without assuming the branch, by
# inverting the frozen outputs: for a sequence whose first emitted row is t=1,
# p_rel(t=1) = sigmoid(alpha * w_0 * (y_0 - 0.5)) with theta_0 = 0, so w_0 — the network's
# own output at that step — is exactly recoverable, one network evaluation per sequence,
# with no recurrence error accumulated. Solving for the standardization parameters against
# those w_0 recovers the pipeline's rule and nothing else.
#
# Kept as data rather than prose so the evidence cannot be quietly softened.
SCALER_RECOVERY_EVIDENCE = {
    "attempted_method": "RECONSTRUCTED_FROM_FROZEN_DATA",
    "outcome": "REPRODUCED_EXACTLY",
    "prior_verdict": ("ACCEL_SPRINT_S5 reported REPRODUCTION_FAILED; that verdict is "
                      "SUPERSEDED. The cause was a mis-modelled forward pass (b_s raw for "
                      "a checkpoint trained with b_s z-scored), not an absent input"),
    # Named by ROLE, never by filename: the product module does not carry model asset
    # paths, and the S4 invariant that enforces that is a real one.
    "artifacts_recovered": (
        "the frozen cohort, the three split files, the IRT parameter file, the three "
        "alpha records, the five per-row experiment outputs and the five checkpoints"),
    "checkpoints_match_frozen_manifest": True,
    "source_tree_completeness": ("S7 recovered the COMPLETE original src/ tree from the "
                                 "archived tarball. The S5 extract was incomplete: it "
                                 "omitted utils/ (which carries load_split), "
                                 "baselines/bkt.py, data/audit_data.py, "
                                 "evaluation/{analysis,corruption}.py and the raw cohort "
                                 "CSV. The four files S5 DID read are byte-identical to "
                                 "the archive copy, so nothing it transcribed was wrong — "
                                 "the tree was just short of the module that defines the "
                                 "split. Recovered: load_split(project, seed) is exactly "
                                 "pd.read_parquet(split_{seed}.parquet), the semantics "
                                 "both S5 and S7 assumed, so no assumption about the "
                                 "train-frame selection is left unverified"),
    "verification": ("every frozen per-row value — y, p_base, p_rel, w_rel — for val AND "
                     "test, for all five checkpoints"),
    "rows_verified": 188262,
    "max_abs_delta": 1.788e-07,
    "delta_is": "float32 network arithmetic; the reproduction is exact to the precision "
                "the frozen run itself used",
    "identifiability": ("the base-42 parameters were recovered by optimisation and then "
                        "compared against the pipeline's own independent re-derivation: "
                        "fitted -0.536745874 / 0.653580144 against re-derived "
                        "-0.536745877 / 0.653580218 (7 significant digits). For the other "
                        "four the optimum is exactly the identity, i.e. the raw column"),
    "per_variant_b_s_mode": dict(B_S_PER_VARIANT),
    "free_fit_was_not_used": ("the S5 free 8-parameter fit (rmse 9.3e-05) is NOT the "
                              "basis of this verdict and is not promoted; the recovery is "
                              "a closed-form inversion corroborated by the pipeline's own "
                              "rule"),
    "forbidden_routes_not_used": list(SCALER_GATE_FORBIDDEN_METHODS),
    "conclusion": ("the exact training transform is PROVEN for all five checkpoints; the "
                   "scaler gate is closed. This does NOT make the component product-usable: "
                   "b_s, log_opp and p_t are still indexed by the scientific skill "
                   "ontology, and that is a separate, independent gate"),
}


def production_mode() -> str:
    """The mode this module reports, DERIVED from the open gates rather than asserted.

    TWO gates now, and passing one does not pass the other:

      * the SCALER gate — can a raw value be scaled into the space the checkpoints were
        trained on?  Closed in S7.
      * the INPUT-COMPATIBILITY gate — can the product construct the vector at all?  Still
        INCOMPATIBLE: b_s / log_opp / p_t are keyed by the scientific skill ontology, and
        no hint signal exists on any surface.

    Deriving the mode from BOTH is what makes a silent promotion impossible: closing the
    scaler gate alone must not, and does not, open the surface. S5's version of this
    function returned PREVIEW on the scaler gate alone, which would have promoted the
    component the moment S7 closed it.
    """
    if SCALER_RECOVERY_METHOD not in SCALER_GATE_ACCEPTED_METHODS:
        return metadata.MODE_SHADOW_NOT_USER_VISIBLE
    if PRODUCT_FEATURE_COMPATIBILITY != "COMPATIBLE":
        return metadata.MODE_SHADOW_NOT_USER_VISIBLE
    return metadata.MODE_PREVIEW

SCORE_SEMANTICS = ("reliability weight w in (0,1) — NOT the probability the response is "
                   "correct, NOT a confidence, NOT a learner judgement, NOT mastery")

# The only permitted user-facing framing for this semantic. It is reported inside the
# requirement block and is NOT surfaced while the mode is SHADOW_NOT_USER_VISIBLE.
USER_FACING_LABEL_ZH = "学习证据可靠度（实验）"

# The exact reasons no product weight is produced. Reason codes are stable identifiers so
# the product surface can be asserted on and cannot silently drift.
BLOCKER_HINTS = "HINT_SIGNAL_NOT_PERSISTED"
BLOCKER_RESPONSE_TIME = "RESPONSE_TIME_NOT_GUARANTEED"
BLOCKER_ATTEMPT_COUNT = "ATTEMPT_COUNT_NOT_GUARANTEED"
BLOCKER_ONTOLOGY = "SKILL_ONTOLOGY_MAPPING_ABSENT"
BLOCKER_B_MAP = "IRT_B_MAP_NOT_BUNDLED"
BLOCKER_STANDARDIZATION = "STANDARDIZATION_STATS_NOT_BUNDLED"
BLOCKER_UPSTREAM_P_T = "UPSTREAM_LEARNER_STATE_P_T_UNAVAILABLE"
BLOCKER_CALIBRATION = "CALIBRATION_GATE_NOT_ESTABLISHED"


def model_requirement() -> dict:
    """What the model needs as INPUT — a REQUIREMENT statement, not a claim of execution."""
    return {
        "component": COMPONENT,
        "scientific_source_class": SCIENTIFIC_SOURCE_CLASS,
        "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
        "variants": dict(SCIENTIFIC_VARIANTS),
        "variant_mode": VARIANT_MODE,
        "active_product_variant": ACTIVE_PRODUCT_VARIANT,
        "replacement_readiness": REPLACEMENT_READINESS,
        "required_input": [
            "y (binary correctness of the interaction)",
            "attempt_gt1 (whether this was a repeat attempt)",
            "has_bottom_hint (whether the bottom hint was used)",
            "hint_count (number of hints used)",
            "log_rt (response time, log-scaled and z-scored)",
            "log_opp (log1p of prior opportunities on the same skill)",
            "b_s (IRT skill difficulty for the interaction's skill)",
            "p_t (the running learner-state prediction at that step)",
        ],
        "available_product_input": [
            "correctness (authoritative boolean, from the canonical event stream)",
            "occurrence order (the event timestamp ordering)",
            "item reference (the question the observation belongs to)",
        ],
        "missing_input": [
            "hint_count", "has_bottom_hint", "log_rt", "attempt_gt1",
            "b_s (IRT skill difficulty)", "log_opp (per-skill opportunity)",
            "p_t (running learner-state prediction)",
        ],
        # S7 closed this entry; kept visible as a RESOLVED requirement rather than deleted.
        "resolved_input": [
            "standardization stats (training mean/std for the z-scored features) — "
            "recovered and verified in ACCEL_SPRINT_S7; see SCALER_STANDARDIZATION_PARAMS",
        ],
        "score_semantics": SCORE_SEMANTICS,
        "scientific_threshold": SCIENTIFIC_THRESHOLD,
        "user_facing_label_zh": USER_FACING_LABEL_ZH,
        "user_facing_label_note": ("the only permitted framing for this semantic; NOT "
                                   "surfaced in this mode"),
        # PART C (S5): the exact input contract, read off the frozen training source.
        "feature_vector": list(FEATURE_VECTOR),
        "feature_schema": [dict(f) for f in FEATURE_SCHEMA],
        "feature_availability": [dict(f) for f in FEATURE_AVAILABILITY],
        "product_feature_compatibility": PRODUCT_FEATURE_COMPATIBILITY,
        "incompatible_features": list(INCOMPATIBLE_FEATURES),
        "standardization": dict(STANDARDIZATION),
        "missing_value_policy": dict(MISSING_VALUE_POLICY),
        "training_pipeline": dict(TRAINING_PIPELINE),
        "source_sha256": dict(SCIENTIFIC_SOURCE_SHA256),
    }


def scaler_gate() -> dict:
    """PART A (S5): whether the training standardizer may be used, and why.

    The gate is deliberately narrow. A scaler is usable only when it was either FOUND as a
    fitted artifact or RE-DERIVED from frozen research bytes. Every other route — fitting
    on product users or on the inference batch, assuming a standard normal, borrowing
    another experiment's statistics, or trying to invert the checkpoint weights — is
    forbidden, and none of them is a lesser version of the accepted ones.
    """
    return {
        "component": COMPONENT,
        "applies_to_features": list(CONT_FEATURES),
        "standardizer_required": True,
        "recovery_method": SCALER_RECOVERY_METHOD,
        "recovery_evidence": SCALER_RECOVERY_EVIDENCE,
        "accepted_methods": list(SCALER_GATE_ACCEPTED_METHODS),
        "forbidden_methods": list(SCALER_GATE_FORBIDDEN_METHODS),
        "missing_artifacts": list(SCALER_RECOVERY_REQUIREMENTS),
        "gate_passed": SCALER_RECOVERY_METHOD in SCALER_GATE_ACCEPTED_METHODS,
        "note": ("without the training mean/std no caller can scale a raw value into the "
                 "space the checkpoints were trained on, and no substitute is admissible"),
    }


def blockers() -> list[str]:
    """The exact, independent reasons no product weight is produced TODAY.

    Two of the eight reasons S4 named have since been closed by measurement
    (``BLOCKER_STANDARDIZATION`` in S5/S7, and ``BLOCKER_B_MAP`` as a *bundling* claim),
    and they are NOT silently dropped: they moved to :func:`resolved_blockers` so the set
    of reasons is still complete and a reader can see which changed and why. Closing them
    did not open the surface, because the input gate is independent.
    """
    return [
        f"{BLOCKER_HINTS}: the product persists no hint signal — the canonical pipeline "
        f"writes hints = None unconditionally, so hint_count and has_bottom_hint have no "
        f"real source",
        f"{BLOCKER_RESPONSE_TIME}: log_rt needs a response time; response_time_ms is a "
        f"nullable column that the historical backfill never sets and live rows do not "
        f"guarantee, and a latency must not be invented",
        f"{BLOCKER_ATTEMPT_COUNT}: attempt_gt1 needs an attempt count; attempt_no is "
        f"nullable and not guaranteed, and an attempt count must not be invented",
        f"{BLOCKER_ONTOLOGY}: log_opp and b_s are indexed by skill_id in the SCIENTIFIC "
        f"ontology, and the product has CS408 knowledge points with no mapping to it",
        f"{BLOCKER_UPSTREAM_P_T}: the dynamic feature p_t is the running prediction of the "
        f"component's own per-(user, skill) theta recurrence and inherits every blocker "
        f"above",
        f"{BLOCKER_CALIBRATION}: the frozen component record carries scientific_threshold "
        f"= null — no calibration/validity threshold was established for this component",
    ]


def resolved_blockers() -> list[dict]:
    """The reasons S4 named that measurement has since CLOSED, each with what closed it.

    Reported rather than deleted: a blocker that disappears without a reason is
    indistinguishable from one that was quietly waived.
    """
    return [
        {"code": BLOCKER_STANDARDIZATION,
         "resolved_by": "ACCEL_SPRINT_S5 derived it; ACCEL_SPRINT_S7 verified it",
         "what_changed": ("the four (mean, std) pairs are re-derived from the frozen cohort "
                          "and split and PROVEN against every frozen per-row output "
                          "(188,262 rows, max |delta| 1.788e-07). They are recorded in "
                          "SCALER_STANDARDIZATION_PARAMS, so a raw value can now be scaled "
                          "into the space the checkpoints were trained on"),
         "what_did_not_change": ("scaling was never the binding constraint — the columns "
                                 "being scaled still have no product source")},
        {"code": BLOCKER_B_MAP,
         "resolved_by": "ACCEL_SPRINT_S5/S7 — recovered and digest-pinned in the archive",
         "what_changed": ("the IRT b_map IS recoverable from the frozen research bytes, so "
                          "the 'not bundled' half of the claim is closed"),
         "what_did_not_change": ("the map is keyed by the SCIENTIFIC skill_id space, so it "
                                 "is not a product input; the residual blocker is "
                                 "BLOCKER_ONTOLOGY, which is why the code does not appear "
                                 "as a separate OPEN reason")},
    ]


def preview(db: DbSession, user_id: int, *, service_namespace: str | None = None,
            exam_module_id: str | None = None, probe_runtime: bool = False,
            client: ScientificClient | None = None) -> dict:
    """Report the evidence_reliability gate for this caller. Never raises, never writes.

    No inference is attempted, because there is no honest input to attempt it with. The
    response states the exact blockers and the real canonical evidence that exists.
    """
    # The evidence window is the SAME real canonical fact set the other components read:
    # an ordered sequence carrying an authoritative boolean verdict. It is defined once,
    # in learner_state, so the two surfaces can never disagree about what the product has.
    from .learner_state import load_evidence_window

    evidence = load_evidence_window(db, user_id, service_namespace=service_namespace,
                                    exam_module_id=exam_module_id)
    gate_blockers = blockers()
    if evidence["event_count"] == 0:
        gate_blockers = gate_blockers + ["NO_ELIGIBLE_PRACTICE_EVENTS_IN_SCOPE"]

    reachable = None
    if probe_runtime:
        # Bounded by construction: ``health`` has its own short timeout and answers
        # "unavailable" rather than raising, and the probe is wrapped anyway. A scientific
        # outage is reported as unreachable, never escalated to a product 500.
        try:
            client = client or get_client()
            reachable = client.health().get("status") == "ok"
        except Exception as exc:  # noqa: BLE001 — a probe may never break the caller
            logger.warning("evidence_reliability runtime probe failed: %s",
                           type(exc).__name__)
            reachable = False

    return {
        "metadata": metadata.metadata(
            component=COMPONENT, mode=metadata.MODE_SHADOW_NOT_USER_VISIBLE,
            runtime_release_id=None, source_class=SCIENTIFIC_SOURCE_CLASS,
            blockers=gate_blockers,
            semantics="a reliability weight — NOT a probability the response is correct "
                      "and NOT a confidence — and no weight is produced in this mode; the "
                      "product surface is closed"),
        "score_semantics": SCORE_SEMANTICS,
        "reliability_weight": None,
        "model_requirement": model_requirement(),
        "scaler_gate": scaler_gate(),
        "evidence_window": evidence,
        "runtime_reachable": reachable,
        "runtime_provenance": {
            "runtime_path": RUNTIME_PATH,
            "scientific_source_class": SCIENTIFIC_SOURCE_CLASS,
            "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
            "model_executes": True,
            "executed_for_this_request": False,
            "note": ("the five checkpoints are real and executable (panel latency ~2 ms, "
                     "deterministic); the panel was NOT executed for this request because "
                     "the honest input does not exist"),
        },
    }
