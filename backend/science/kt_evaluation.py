"""Evaluation primitives for a CS408-native KT model — pure Python, zero heavy imports.

WHY THIS IS PURE PYTHON
-----------------------
The product backend cannot import the scientific stack (measured: no numpy / torch / scipy
/ pandas in ``backend/.venv``), and that is a PROPERTY to keep, not a limitation to work
around — it is what makes it physically impossible for a model to run inside a web request.
So the metrics and the evaluator a product surface needs are implemented here in the
standard library, and everything that needs numpy lives in the offline training
environment.

WHAT IS HERE
------------
    PART G  metrics — AUROC, accuracy, NLL / log loss, Brier, ECE with reliability bins,
            and the same set computed PER GROUP (per module, per user) with sample counts.
    PART H  calibration — Platt, isotonic and temperature, fitted on dev ONLY, evaluated
            on an untouched test split, with the fit provenance persisted as data.
    PART N  the online shadow evaluator — pairs a shadow prediction with the NEXT observed
            authoritative response and scores them. No intervention, no product control,
            and it never writes.

THE ONE RULE THAT MATTERS
-------------------------
``y`` is an authoritative boolean and ``p`` is a probability in [0, 1]. Nothing here
tolerates a None masquerading as a negative label: a prediction whose target was never
observed is EXCLUDED and COUNTED, because scoring it as "wrong" would be the same class of
error as reading an unanswered item as incorrect.
"""
from __future__ import annotations

import hashlib
import json
import math

# ============================================================ PART G — metrics


def _clean(pairs) -> tuple[list[float], list[float], int]:
    """Split into (y, p) keeping only rows that carry BOTH a boolean and a finite
    probability. Returns the count dropped, so an exclusion is never silent."""
    y: list[float] = []
    p: list[float] = []
    dropped = 0
    for target, prob in pairs:
        if not isinstance(target, bool):
            dropped += 1
            continue
        try:
            value = float(prob)
        except (TypeError, ValueError):
            dropped += 1
            continue
        if not math.isfinite(value):
            dropped += 1
            continue
        y.append(1.0 if target else 0.0)
        p.append(min(1.0, max(0.0, value)))
    return y, p, dropped


def auroc(y: list[float], p: list[float]) -> float | None:
    """Rank-based AUROC with mid-ranks for ties. None when one class is absent.

    None rather than 0.5: a single-class sample has no ranking to measure, and reporting
    chance would invent a result.
    """
    positives = sum(1 for v in y if v == 1.0)
    negatives = len(y) - positives
    if positives == 0 or negatives == 0:
        return None
    order = sorted(range(len(p)), key=lambda i: p[i])
    ranks = [0.0] * len(p)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and p[order[j + 1]] == p[order[i]]:
            j += 1
        mid = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    rank_sum = sum(ranks[i] for i in range(len(y)) if y[i] == 1.0)
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def log_loss(y: list[float], p: list[float], eps: float = 1e-7) -> float | None:
    if not y:
        return None
    total = 0.0
    for target, prob in zip(y, p):
        q = min(1.0 - eps, max(eps, prob))
        total += -(target * math.log(q) + (1.0 - target) * math.log(1.0 - q))
    return total / len(y)


def brier(y: list[float], p: list[float]) -> float | None:
    if not y:
        return None
    return sum((prob - target) ** 2 for target, prob in zip(y, p)) / len(y)


def accuracy(y: list[float], p: list[float], threshold: float = 0.5) -> float | None:
    if not y:
        return None
    hits = sum(1 for target, prob in zip(y, p)
               if (prob >= threshold) == (target == 1.0))
    return hits / len(y)


def reliability_bins(y: list[float], p: list[float], bins: int = 10) -> list[dict]:
    """The per-bin table ECE is computed from, reported so the number can be inspected."""
    if bins < 1:
        raise ValueError("bins must be >= 1")
    table = []
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        members = [i for i, prob in enumerate(p)
                   if (low <= prob < high) or (index == bins - 1 and prob >= high)]
        if not members:
            table.append({"bin": index, "low": low, "high": high, "n": 0,
                          "mean_predicted": None, "observed_rate": None, "gap": None})
            continue
        mean_predicted = sum(p[i] for i in members) / len(members)
        observed = sum(y[i] for i in members) / len(members)
        table.append({"bin": index, "low": low, "high": high, "n": len(members),
                      "mean_predicted": mean_predicted, "observed_rate": observed,
                      "gap": abs(observed - mean_predicted)})
    return table


def ece(y: list[float], p: list[float], bins: int = 10) -> float | None:
    """Expected calibration error: |observed - predicted| averaged over bins, weighted by
    bin population. None on an empty sample rather than 0.0, which would read as perfect
    calibration."""
    if not y:
        return None
    total = 0.0
    table = reliability_bins(y, p, bins=bins)
    for row in table:
        if row["n"]:
            total += (row["n"] / len(y)) * row["gap"]
    return total


def classification_metrics(y: list[float], p: list[float], bins: int = 10) -> dict:
    """The required metric set, plus the sample counts it was computed on."""
    return {
        "n": len(y),
        "positives": int(sum(1 for v in y if v == 1.0)),
        "negatives": int(sum(1 for v in y if v == 0.0)),
        "auroc": auroc(y, p),
        "accuracy": accuracy(y, p),
        "log_loss": log_loss(y, p),
        "nll": log_loss(y, p),          # the same quantity under its other standard name
        "brier": brier(y, p),
        "ece": ece(y, p, bins=bins),
        "reliability_bins": reliability_bins(y, p, bins=bins),
        "majority_class_rate": (
            max(sum(1 for v in y if v == 1.0), sum(1 for v in y if v == 0.0)) / len(y)
            if y else None),
    }


def metrics_from_pairs(pairs, bins: int = 10) -> dict:
    y, p, dropped = _clean(pairs)
    out = classification_metrics(y, p, bins=bins)
    out["excluded_rows"] = dropped
    out["exclusion_rule"] = ("a row without an authoritative boolean target or without a "
                             "finite probability is EXCLUDED and counted, never scored")
    return out


def grouped_metrics(pairs, groups, bins: int = 10, min_n: int = 1) -> dict:
    """Per-group metrics (PART G: per-module, and user-grouped test metrics).

    A group below ``min_n`` is reported with its count and NO metrics: a metric computed on
    three rows is noise wearing a number's clothes.
    """
    buckets: dict[str, list] = {}
    for (target, prob), group in zip(pairs, groups):
        buckets.setdefault(str(group), []).append((target, prob))
    out: dict[str, dict] = {}
    for name in sorted(buckets):
        members = buckets[name]
        if len(members) < min_n:
            out[name] = {"n": len(members), "metrics": None,
                         "reason": f"below min_n={min_n}; reporting a metric here would "
                                   f"be noise"}
            continue
        out[name] = {"n": len(members), "metrics": metrics_from_pairs(members, bins=bins)}
    return out


# ============================================================ PART H — calibration
#
# Fitted on DEV ONLY. A calibrator fitted on the test split is not a calibration, it is a
# second chance to fit the test set, and it would make the reported ECE meaningless.
CALIBRATION_METHODS = ("PLATT", "ISOTONIC", "TEMPERATURE")
CALIBRATION_FIT_SPLIT = "dev"
CALIBRATION_EVAL_SPLIT = "test"


def _logit(p: float, eps: float = 1e-7) -> float:
    q = min(1.0 - eps, max(eps, float(p)))
    return math.log(q / (1.0 - q))


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _fit_platt(y: list[float], p: list[float], iters: int = 200, lr: float = 0.1) -> dict:
    """Logistic calibration on the logit: p' = sigmoid(a * logit(p) + b). Plain gradient
    descent — the problem is 2-dimensional and convex, so no library is warranted."""
    if not y:
        raise ValueError("cannot fit a calibrator on an empty sample")
    a, b = 1.0, 0.0
    n = len(y)
    for _ in range(iters):
        ga = gb = 0.0
        for target, prob in zip(y, p):
            z = a * _logit(prob) + b
            error = _sigmoid(z) - target
            ga += error * _logit(prob)
            gb += error
        a -= lr * ga / n
        b -= lr * gb / n
    return {"a": a, "b": b}


def _fit_temperature(y: list[float], p: list[float], iters: int = 200,
                     lr: float = 0.1) -> dict:
    """p' = sigmoid(logit(p) / T). A single scale parameter."""
    if not y:
        raise ValueError("cannot fit a calibrator on an empty sample")
    t = 1.0
    n = len(y)
    for _ in range(iters):
        g = 0.0
        for target, prob in zip(y, p):
            z = _logit(prob) / t
            g += (_sigmoid(z) - target) * (-_logit(prob) / (t * t))
        t -= lr * g / n
        t = max(0.05, min(20.0, t))     # bounded, so a degenerate fit cannot explode
    return {"T": t}


def _fit_isotonic(y: list[float], p: list[float]) -> dict:
    """Pool-adjacent-violators. Returns the fitted step function as breakpoints."""
    if not y:
        raise ValueError("cannot fit a calibrator on an empty sample")
    order = sorted(range(len(p)), key=lambda i: p[i])
    xs = [p[i] for i in order]
    ys = [y[i] for i in order]
    weights = [1.0] * len(xs)
    # PAV
    values = list(ys)
    counts = list(weights)
    i = 0
    while i < len(values) - 1:
        if values[i] > values[i + 1]:
            total = values[i] * counts[i] + values[i + 1] * counts[i + 1]
            merged = counts[i] + counts[i + 1]
            values[i] = total / merged
            counts[i] = merged
            del values[i + 1]
            del counts[i + 1]
            del xs[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1
    return {"x": xs, "y": values}


def fit_calibrator(method: str, y_dev: list[float], p_dev: list[float],
                   *, dev_split_digest: str | None = None) -> dict:
    """Fit on dev and return the calibrator WITH its provenance as data."""
    if method not in CALIBRATION_METHODS:
        raise ValueError(f"unknown calibration method: {method}")
    if method == "PLATT":
        params = _fit_platt(y_dev, p_dev)
    elif method == "TEMPERATURE":
        params = _fit_temperature(y_dev, p_dev)
    else:
        params = _fit_isotonic(y_dev, p_dev)

    payload = json.dumps({"method": method, "params": params}, sort_keys=True,
                         separators=(",", ":"))
    return {
        "method": method,
        "params": params,
        "fitted_on": CALIBRATION_FIT_SPLIT,
        "evaluated_on": CALIBRATION_EVAL_SPLIT,
        "fit_samples": len(y_dev),
        "fit_split_digest": dev_split_digest,
        "calibrator_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "rule": ("fitted on dev ONLY; the test split is untouched by the fit, and the "
                 "calibrated ECE must be reported on test"),
    }


def apply_calibrator(calibrator: dict, probabilities: list[float]) -> list[float]:
    """Apply a fitted calibrator. Deterministic; pure."""
    method = calibrator.get("method")
    params = calibrator.get("params") or {}
    if method == "PLATT":
        a, b = float(params["a"]), float(params["b"])
        return [_sigmoid(a * _logit(p) + b) for p in probabilities]
    if method == "TEMPERATURE":
        t = float(params["T"])
        return [_sigmoid(_logit(p) / t) for p in probabilities]
    if method == "ISOTONIC":
        xs, ys = params.get("x") or [], params.get("y") or []
        if not xs:
            return list(probabilities)
        out = []
        for p in probabilities:
            # step function: the value at the largest breakpoint <= p, else the first value
            value = ys[0]
            for x, yv in zip(xs, ys):
                if p >= x:
                    value = yv
                else:
                    break
            out.append(min(1.0, max(0.0, float(value))))
        return out
    raise ValueError(f"unknown calibration method: {method}")


# ============================================================ PART N — ONLINE EVALUATOR
#
# The scientific validation loop: a SHADOW prediction is scored against the NEXT observed
# authoritative response. It reads; it never writes, never intervenes, and never controls
# anything. Its whole product is a measurement.

ONLINE_EVALUATOR_VERSION = "cs408-kt-shadow-evaluator-v1"
NO_TARGET_OBSERVED = "NO_LATER_AUTHORITATIVE_RESPONSE"


def evaluate_shadow(predictions: list[dict], outcomes: list[dict], *,
                    bins: int = 10, min_group_n: int = 1) -> dict:
    """Score shadow predictions against later observed facts. Deterministic and pure.

    A prediction is ``{"prediction_id", "learner_ref", "concept_key", "predicted_at",
    "probability"}`` and an outcome is ``{"event_id", "learner_ref", "concept_key",
    "occurred_at", "correct"}``.

    A prediction is paired with the EARLIEST authoritative response from the SAME learner
    on the SAME concept strictly after ``predicted_at`` — the next response, not any
    response. A prediction with no such response is excluded and counted; it is never
    scored as a miss, because "we do not know yet" and "we were wrong" are different
    results and only one of them is evidence.

    A non-boolean ``correct`` is not a target: ``None`` (ungraded) and a missing field are
    both excluded, which is the same tri-state rule the dataset contract applies.
    """
    if not isinstance(predictions, list) or not isinstance(outcomes, list):
        raise TypeError("predictions and outcomes must be lists")

    indexed: dict[tuple[str, str], list[dict]] = {}
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        key = (str(outcome.get("learner_ref")), str(outcome.get("concept_key")))
        indexed.setdefault(key, []).append(outcome)
    for bucket in indexed.values():
        bucket.sort(key=lambda o: (float(o.get("occurred_at") or 0.0),
                                   str(o.get("event_id") or "")))

    pairs: list[tuple[bool, float]] = []
    groups: list[str] = []
    paired_ids: list[str] = []
    unmatched: list[str] = []
    observations: list[dict] = []

    well_formed = [p for p in predictions if isinstance(p, dict)]
    # a malformed row is dropped HERE rather than in the sort key: a failure-isolated
    # evaluator must not take the whole run down because one row is not a dict
    for prediction in sorted(well_formed, key=lambda r: str(r.get("prediction_id"))):
        pid = str(prediction.get("prediction_id"))
        key = (str(prediction.get("learner_ref")), str(prediction.get("concept_key")))
        at = float(prediction.get("predicted_at") or 0.0)
        target = None
        for outcome in indexed.get(key, []):
            if float(outcome.get("occurred_at") or 0.0) > at:
                target = outcome
                break
        if target is None or not isinstance(target.get("correct"), bool):
            unmatched.append(pid)
            continue
        pairs.append((target["correct"], prediction.get("probability")))
        groups.append(key[1])
        paired_ids.append(pid)
        observations.append({
            "prediction_id": pid,
            "target_event_id": target.get("event_id"),
            "target_occurred_at": target.get("occurred_at"),
            "target_correct": target["correct"],
            "concept_key": key[1],
        })

    overall = metrics_from_pairs(pairs, bins=bins) if pairs else {
        "n": 0, "auroc": None, "accuracy": None, "log_loss": None, "nll": None,
        "brier": None, "ece": None, "reliability_bins": [], "excluded_rows": 0,
    }

    return {
        "evaluator_version": ONLINE_EVALUATOR_VERSION,
        "role": ("SHADOW evaluation — measurement only. No intervention, no product "
                 "control, and no learner fact is written"),
        "predictions_received": len([p for p in predictions if isinstance(p, dict)]),
        "predictions_paired": len(pairs),
        "predictions_without_target": len(unmatched),
        "unmatched_reason_code": NO_TARGET_OBSERVED,
        "unmatched_rule": ("a prediction with no LATER authoritative response is excluded "
                           "and counted; 'not observed yet' is not an incorrect prediction"),
        "overall": overall,
        "per_concept": grouped_metrics(pairs, groups, bins=bins, min_n=min_group_n) if pairs else {},
        "observations": observations,
        "wrote_learner_fact": False,
        "controls_product_decision": False,
    }


def evaluator_is_ready() -> dict:
    """What the loop needs that the product DOES have, versus what it does not.

    Reported so "the evaluator exists" is never confused with "the loop is running": with
    no shadow predictions recorded, the evaluator has nothing to score and says so.
    """
    return {
        "evaluator_version": ONLINE_EVALUATOR_VERSION,
        "available": True,
        "needs": ["shadow predictions", "canonical facts carrying a boolean verdict"],
        "blocked_by": [],       # nothing structural: it is a pure function of two inputs
        "note": ("the loop is ARMED, not RUNNING. With no model promoted to shadow there "
                 "are no predictions to compare, and an empty comparison is reported as "
                 "n=0 rather than as a result"),
    }
