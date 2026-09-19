"""Re-derive the evidence_reliability training standardizer from FROZEN research bytes.

WHAT THIS IS
------------
The five ``reliability_net_*.pt`` checkpoints consume an ALREADY-STANDARDIZED feature
vector. The standardizer was never serialized: the training driver computes it in-process,
on first call, and reuses it unchanged for val and test. So the numbers exist nowhere on
disk — but they are DETERMINISTIC given three frozen inputs, and this tool re-derives them
from exactly those inputs and nothing else.

THE THREE INPUTS, AND WHY EACH IS REQUIRED
------------------------------------------
  1. ``cohort.parquet``          the frozen cohort the split was drawn from. Carries
                                 ``log_rt`` and ``hint_count`` directly, and the
                                 ``opportunity`` / ``skill_id`` columns the other two
                                 standardized features are derived from.
  2. ``split_{seed}.parquet``    the user-disjoint partition. The standardizer is computed
                                 over the TRAIN USERS of THIS SEED — variant ``42`` and
                                 variant ``43`` do NOT share statistics.
  3. ``irt_skill_params.json``   supplies ``b_1pl``, which ``b_s`` is built from. ``b_s``
                                 is itself one of the four standardized columns, so
                                 without it the column cannot be formed, let alone scaled.

WHAT THIS TOOL REFUSES TO DO
----------------------------
It fits nothing on product data, on a test split, or on any inference batch; it assumes
nothing about the distribution; it borrows no statistics from another experiment; and it
never reads the checkpoint weights. Those routes are enumerated as forbidden in
``science.evidence_reliability.SCALER_GATE_FORBIDDEN_METHODS`` and this tool implements
none of them.

REPRODUCIBILITY
---------------
The pipeline is transcribed from the frozen training source, not remembered:
``build_splits.load_cohort`` defines the cohort, ``run_experiment.main`` defines the derived
columns and the train-row selection, and ``evidence_reliability.build_sequences`` defines
the four (mean, std) pairs. Every input's sha256, the source files' sha256 and this
script's own sha256 are written into the artifact, so a later reader can re-run it and get
the same bytes or find out exactly which input changed.

Run it with a Python that has pandas + pyarrow (the research environment), NOT the product
backend venv::

    D:/ZhixueAI/envs/runtime/Scripts/python.exe scripts/reconstruct_evidence_reliability_scaler.py \
        --project D:/ZhixueAI/research_extract/evidence_reliability \
        --research-src D:/ZhixueAI/research_extract/evidence_reliability/src \
        --seeds 42,43,44 --out evidence_reliability_scaler.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Transcribed from the frozen model module. Order matters: it is the order the vector uses.
CONT_FEATS = ["log_rt", "hint_count", "log_opp", "b_s"]
BIN_FEATS = ["y", "attempt_gt1", "has_bottom_hint"]
STATIC_ORDER = BIN_FEATS + CONT_FEATS

# The source files these facts were read from, relative to the research ``src`` root.
SOURCE_FILES = (
    "models/evidence_reliability.py",
    "evaluation/run_experiment.py",
    "data/build_splits.py",
    "baselines/irt.py",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def derive_for_seed(cohort_path: Path, split_path: Path, b_map: dict,
                    seed: int) -> dict:
    """The four (mean, std) pairs, exactly as the training driver would compute them."""
    import numpy as np
    import pandas as pd

    cohort = pd.read_parquet(cohort_path)
    split = pd.read_parquet(split_path)

    # run_experiment.main: the derived columns, on a copy of the cohort
    c = cohort.copy()
    c["y"] = c["correct"].astype("int8")
    c["log_opp"] = np.log1p(c["opportunity"])
    c["b_s"] = c["skill_id"].map(b_map).fillna(0.0)

    # run_experiment.main: rows_of("train") — every cohort row for a train USER
    train_user_ids = set(split[split["split"] == "train"]["user_id"].unique())
    train_df = c[c["user_id"].isin(train_user_ids)]

    # evidence_reliability.build_sequences, first call: the standardizer is fixed here
    mean = {col: float(train_df[col].mean()) for col in CONT_FEATS}
    std = {col: float(train_df[col].std()) or 1.0 for col in CONT_FEATS}

    return {
        "seed": seed,
        "train_rows": int(len(train_df)),
        "train_users": int(train_df["user_id"].nunique()),
        "mean": mean,
        "std": std,
        "feature_order": STATIC_ORDER + ["p_t"],
        "standardized_features": CONT_FEATS,
        "raw_features": BIN_FEATS + ["p_t"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True,
                        help="the frozen evidence_reliability project dir")
    parser.add_argument("--research-src", default=None,
                        help="the src/ dir the pipeline was transcribed from")
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    project = Path(args.project)
    src = Path(args.research_src) if args.research_src else project / "src"

    cohort_path = project / "data" / "splits" / "cohort.parquet"
    irt_path = project / "results" / "irt_skill_params.json"
    for required in (cohort_path, irt_path):
        if not required.is_file():
            print(f"REFUSING: required frozen input missing: {required}", file=sys.stderr)
            return 2

    b_map = json.loads(irt_path.read_text(encoding="utf-8"))["b_1pl"]

    seeds = [int(s) for s in args.seeds.split(",")]
    variants_by_seed = {"42": ["42", "42_nort", "42_surprise"], "43": ["43"], "44": ["44"]}
    per_seed = {}
    for seed in seeds:
        split_path = project / "data" / "splits" / f"split_{seed}.parquet"
        if not split_path.is_file():
            print(f"REFUSING: required frozen split missing: {split_path}", file=sys.stderr)
            return 2
        derived = derive_for_seed(cohort_path, split_path, b_map, seed)
        derived["variants"] = variants_by_seed.get(str(seed), [])
        derived["split_sha256"] = sha256_file(split_path)
        per_seed[str(seed)] = derived

    source_hashes = {}
    for rel in SOURCE_FILES:
        path = src / rel
        source_hashes[rel] = sha256_file(path) if path.is_file() else None

    artifact = {
        "artifact": "evidence_reliability_training_standardizer",
        "artifact_version": 1,
        "recovery_method": "RECONSTRUCTED_FROM_FROZEN_DATA",
        "component": "evidence_reliability",
        "cohort_sha256": sha256_file(cohort_path),
        "irt_skill_params_sha256": sha256_file(irt_path),
        "preprocessing_source_sha256": source_hashes,
        "reconstruction_script_sha256": sha256_file(Path(__file__)),
        "formula": "z = (value - mean) / std, applied to the continuous block ONLY",
        "std_convention": "pandas Series.std() == sample std (ddof=1), with `or 1.0` guard",
        "mean_std_source": "the TRAIN-user rows of that seed's split",
        "per_seed": per_seed,
        "forbidden_routes_not_used": [
            "FIT_ON_PRODUCT_USERS", "FIT_ON_TEST_SPLIT", "FIT_ON_INFERENCE_BATCH",
            "ASSUME_STANDARD_NORMAL", "COPY_FROM_OTHER_EXPERIMENT",
            "DERIVE_FROM_CHECKPOINT",
        ],
    }
    out = Path(args.out)
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[written] {out}")
    for seed, derived in per_seed.items():
        print(f"  seed {seed}: train_rows={derived['train_rows']} "
              f"mean={ {k: round(v, 6) for k, v in derived['mean'].items()} }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
