"""Build the immutable Scientific Runtime deployment artifact from the frozen closure.

Source of truth: D:\\ZhixueAI (frozen scientific runtime). This script produces a
deterministic .tar.gz + .sha256 + .manifest.json under deploy/artifacts/. The generated
files are GENERATED_DEPLOYMENT_ARTIFACT — edit only by regenerating from the source.

Usage:
    python deploy/build_runtime_artifact.py [closure_dir] [output_dir]
"""
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
from datetime import datetime, timezone

ARTIFACT_ID = "zhixue-runtime-v1-phase1gr-p1-student-twin"
RUNTIME_RELEASE_ID = "zhixue-runtime-v1-phase1gr-p1"
COMPONENT = "student_twin"
SCIENTIFIC_SOURCE_COMMIT = "a16efa27aac90d9c8d8d9ee703aefe5919f4839e"
ENGINEERING_PATCH_TYPE = "ENGINEERING_PACKAGING_ONLY"

DEFAULT_CLOSURE = r"D:\ZhixueAI\runtime_package\v1\closure\zhixue-runtime-v1-phase1gr-student-twin"


def collect_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in ("__pycache__", ".git", ".venv", "venv")]
        for fn in sorted(filenames):
            if fn.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            files.append((rel, full))
    return sorted(files)


def build_tar_bytes(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for rel, full in files:
            info = tf.gettarinfo(full, arcname=rel)
            # deterministic metadata: fixed mtime, no uid/gid/uname leakage
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            with open(full, "rb") as f:
                tf.addfile(info, f)
    return buf.getvalue()


def main():
    closure = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CLOSURE
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "artifacts")
    os.makedirs(out_dir, exist_ok=True)

    files = collect_files(closure)
    tar_bytes = build_tar_bytes(files)
    archive_bytes = gzip.compress(tar_bytes, mtime=0)

    archive_path = os.path.join(out_dir, f"{ARTIFACT_ID}.tar.gz")
    with open(archive_path, "wb") as f:
        f.write(archive_bytes)

    archive_sha = hashlib.sha256(archive_bytes).hexdigest()
    with open(os.path.join(out_dir, f"{ARTIFACT_ID}.sha256"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{archive_sha}  {ARTIFACT_ID}.tar.gz\n")

    file_hashes = {
        rel: hashlib.sha256(open(full, "rb").read()).hexdigest()
        for rel, full in files
    }
    scientific_hashes = {
        rel: h for rel, h in file_hashes.items()
        if rel.startswith("runtime_src/v1/student_twin/")
    }
    uncompressed = sum(os.path.getsize(full) for _rel, full in files)

    manifest = {
        "artifact_id": ARTIFACT_ID,
        "runtime_release_id": RUNTIME_RELEASE_ID,
        "component": COMPONENT,
        "source_root": closure,
        "file_count": len(files),
        "uncompressed_size": uncompressed,
        "archive_sha256": archive_sha,
        "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
        "scientific_source_hashes": scientific_hashes,
        "engineering_patch_type": ENGINEERING_PATCH_TYPE,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python_requirement": ["numpy"],
        "platform_target": "linux-x86_64",
        "generated_deployment_artifact": True,
        "source_of_truth": "D:\\ZhixueAI",
        "edit_in_product_repo": "FORBIDDEN",
    }
    with open(os.path.join(out_dir, f"{ARTIFACT_ID}.manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"artifact: {archive_path}")
    print(f"  files: {len(files)}  uncompressed: {uncompressed} bytes")
    print(f"  sha256: {archive_sha}")


if __name__ == "__main__":
    main()
