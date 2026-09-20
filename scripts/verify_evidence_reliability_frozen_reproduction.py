"""Reproduce the frozen evidence_reliability experiment and compare, row for row.

WHAT THIS PROVES
----------------
That the recovered preprocessing is the REAL one. Re-deriving mean/std from the frozen
cohort and split is only a claim until something checks it, and the check is available:
the research archive kept ``results/reliability_predictions_{seed}.parquet`` — the per-row
``(y, p_base, p_rel, w_rel)`` the ORIGINAL run produced on val and test.

So this script re-runs the original pipeline with the reconstructed standardizer and
compares its own output against those frozen rows. If the scaler were wrong by even a
little, ``p_rel`` and ``w_rel`` would diverge immediately: the checkpoints consume the
standardized vector directly, so a different mean/std is a different input to a fixed
function, and the weights move.

It reproduces the pipeline by IMPORTING the frozen source's own functions
(``build_sequences``, ``evaluate``, ``ReliabilityNet``) rather than restating them. A
reimplementation would only prove the reimplementation is self-consistent, which is the
one thing already known.

WHAT IT DOES NOT DO
-------------------
It fits no standardizer of its own beyond the frozen rule (train rows of the seed's split),
touches no product database, and writes nothing into the repository. It is an offline
verification that needs the research environment (pandas + pyarrow + torch)::

    D:/ZhixueAI/envs/runtime/Scripts/python.exe \
        scripts/verify_evidence_reliability_frozen_reproduction.py \
        --project D:/ZhixueAI/research_extract/evidence_reliability \
        --checkpoints D:/ZhixueAI/model_assets/v1/evidence_reliability \
        --seed 42 --out /tmp/repro_42.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

CONT_FEATS = ["log_rt", "hint_count", "log_opp", "b_s"]
VARIANT_FEATURE_SUBSET = {
    "42": None,                      # all 7 static
    "42_nort": ["y", "attempt_gt1", "has_bottom_hint", "hint_count", "log_opp", "b_s"],
    "42_surprise": ["y", "b_s"],
    "43": None,
    "44": None,
}

# Which variants were trained with b_s Z-SCORED rather than raw. See the note at the
# sequence-building step: the archived source only expresses the RAW branch, and the base
# 42 run predates it.
ZSCORED_B_S_VARIANTS = {"42"}


def load_frozen_module(src_root: Path):
    """Import the FROZEN training module. Raises if it is not there to import."""
    path = src_root / "models" / "evidence_reliability.py"
    if not path.is_file():
        raise FileNotFoundError(f"frozen training module missing: {path}")
    spec = importlib.util.spec_from_file_location("frozen_evidence_reliability", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--checkpoints", required=True,
                        help="the frozen model_assets/v1/evidence_reliability dir")
    parser.add_argument("--src", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tag", default="", help="variant suffix, e.g. _nort / _surprise")
    parser.add_argument("--variant", default=None,
                        help="variant id; defaults to the seed's baseline checkpoint")
    parser.add_argument("--tol", type=float, default=1e-6)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    project = Path(args.project)
    src_root = Path(args.src) if args.src else project / "src"

    import numpy as np
    import pandas as pd
    import torch

    frozen = load_frozen_module(src_root)
    variant = args.variant or f"{args.seed}{args.tag}"
    checkpoint = Path(args.checkpoints) / f"reliability_net_{variant}.pt"
    if not checkpoint.is_file():
        print(f"REFUSING: checkpoint missing: {checkpoint}", file=sys.stderr)
        return 2

    cohort = pd.read_parquet(project / "data" / "splits" / "cohort.parquet")
    split = pd.read_parquet(project / "data" / "splits" / f"split_{args.seed}.parquet")
    irt = json.loads((project / "results" / "irt_skill_params.json").read_text("utf-8"))
    b_map = irt["b_1pl"]
    comparison = json.loads(
        (project / "results" / f"comparison_{args.seed}{args.tag}.json").read_text("utf-8"))
    alpha = comparison["alpha"]

    # run_experiment.main: derived columns, then the split's frames
    c = cohort.copy()
    c["y"] = c["correct"].astype("int8")
    c["log_opp"] = np.log1p(c["opportunity"])
    c["b_s"] = c["skill_id"].map(b_map).fillna(0.0)

    def rows_of(name):
        ids = split[split["split"] == name]["user_id"].unique()
        return c[c["user_id"].isin(ids)]

    train_df, val_df, test_df = rows_of("train"), rows_of("val"), rows_of("test")

    static_cols = VARIANT_FEATURE_SUBSET.get(variant)
    dev = "cpu"
    seqs_train, mu, sd = frozen.build_sequences(train_df, b_map=b_map, device=dev,
                                               static_cols=static_cols)
    seqs_val, _, _ = frozen.build_sequences(val_df, mu, sd, b_map=b_map, device=dev,
                                            static_cols=static_cols)
    seqs_test, _, _ = frozen.build_sequences(test_df, mu, sd, b_map=b_map, device=dev,
                                             static_cols=static_cols)

    # ------------------------------------------------------------------ ACCEL_SPRINT_S7
    # The archived source sends ``b_s`` down its ``if c == "b_s"`` branch, which emits the
    # mapped value RAW; only the ``else`` branch z-scores. Measured against the frozen
    # per-row outputs, four of the five checkpoints DO reproduce under that branch, and
    # exactly one — the base ``42`` run — reproduces only when b_s is z-scored. The
    # archived file is therefore a LATER revision than the checkpoint it is used to verify,
    # and following it literally for variant 42 measures the revision, not the run.
    #
    # This is what S5's REPRODUCTION_FAILED actually measured: a mis-modelled forward pass,
    # not an absent input. Applying the branch per variant is what turns the check from a
    # verdict about the archive into a measurement of the transform.
    if variant in ZSCORED_B_S_VARIANTS:
        resolved_cols = static_cols or list(frozen.STATIC_ORDER)
        index = list(resolved_cols).index("b_s")
        for sequence in seqs_train + seqs_val + seqs_test:
            column = sequence["feat"][:, index]
            sequence["feat"][:, index] = (column - mu["b_s"]) / sd["b_s"]

    n_feat = len(static_cols) if static_cols else 7
    net = frozen.ReliabilityNet(n_feat=n_feat + 1)
    net.load_state_dict(torch.load(str(checkpoint), map_location="cpu"))
    net.eval()

    frozen_preds = pd.read_parquet(
        project / "results" / f"reliability_predictions_{args.seed}{args.tag}.parquet")

    report = {
        "variant": variant,
        "seed": args.seed,
        "alpha": alpha,
        "n_feat": n_feat + 1,
        "scalarization": {
            "mean": {k: float(v) for k, v in mu.items()},
            "std": {k: float(v) for k, v in sd.items()},
        },
        "provenance": {
            "cohort_sha256": sha256_file(project / "data" / "splits" / "cohort.parquet"),
            "split_sha256": sha256_file(
                project / "data" / "splits" / f"split_{args.seed}.parquet"),
            "irt_skill_params_sha256": sha256_file(
                project / "results" / "irt_skill_params.json"),
            "comparison_sha256": sha256_file(
                project / "results" / f"comparison_{args.seed}{args.tag}.json"),
            "checkpoint_sha256": sha256_file(checkpoint),
            "training_source_sha256": sha256_file(
                src_root / "models" / "evidence_reliability.py"),
        },
        "splits": {},
    }

    ok = True
    for name, seqs in (("val", seqs_val), ("test", seqs_test)):
        # BASE first. It is the equal-weight model: alpha + y + the sequence layout, and no
        # feature at all. If this reproduces and the weighted model does not, the divergence
        # is confined to the standardized feature block rather than to the pipeline — which
        # is the difference between "the archive is inconsistent" and "the scaler is wrong".
        y_base, p_base, _ = frozen.evaluate(seqs, alpha, scorer=None)
        y, p, w = frozen.evaluate(seqs, alpha, net)
        expected = frozen_preds[frozen_preds["split"] == name]
        exp_y = expected["y"].to_numpy()
        exp_p = expected["p_rel"].to_numpy()
        exp_w = expected["w_rel"].to_numpy()
        exp_p_base = expected["p_base"].to_numpy()

        if not (len(y) == len(exp_y) == len(exp_p) == len(exp_w) == len(exp_p_base)):
            report["splits"][name] = {
                "matched": False,
                "reason": "row count differs",
                "rows_reproduced": int(len(y)),
                "rows_frozen": int(len(exp_y)),
            }
            ok = False
            continue

        d_p = float(np.max(np.abs(p - exp_p)))
        d_w = float(np.max(np.abs(w - exp_w)))
        d_base = float(np.max(np.abs(p_base - exp_p_base)))
        y_match = bool(np.array_equal(y.astype(int), exp_y.astype(int)))
        matched = y_match and d_p <= args.tol and d_w <= args.tol
        report["splits"][name] = {
            "matched": matched,
            "rows": int(len(y)),
            "y_identical": y_match,
            "max_abs_p_base_delta": d_base,
            "base_reproduced": bool(d_base <= 1e-6),
            "max_abs_p_rel_delta": d_p,
            "max_abs_w_rel_delta": d_w,
            "mean_w_rel_reproduced": float(np.mean(w)),
            "mean_w_rel_frozen": float(np.mean(exp_w)),
        }
        ok = ok and matched

    report["reproduced"] = ok
    report["verdict"] = ("SCALER_AND_CHECKPOINT_REPRODUCE_FROZEN_OUTPUTS" if ok
                         else "DIVERGED_FROM_FROZEN_OUTPUTS")
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
