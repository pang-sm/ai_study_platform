# Runtime Deployment Artifacts

These files are **immutable deployment artifacts** for the Scientific Runtime Service.

- `zhixue-runtime-v1-phase1gr-p1-student-twin.tar.gz` — deterministic archive of the
  minimal StudentTwin runtime closure (zhixue_runtime package + student_twin source +
  manifest + assets; NO heavy model assets, NO `.pyc`, NO `.git`, NO venv, NO secrets).
- `zhixue-runtime-v1-phase1gr-p1-student-twin.sha256` — the archive SHA-256.
- `zhixue-runtime-v1-phase1gr-p1-student-twin.manifest.json` — provenance manifest.

## Rules

1. These files are **NOT** scientific source-of-truth.
2. Source-of-truth = `D:\ZhixueAI` (frozen scientific runtime).
3. **EDIT_IN_PRODUCT_REPO = FORBIDDEN** — never hand-edit the archive or manifest.
4. Regenerate only via `python deploy/build_runtime_artifact.py` (from the frozen closure),
   then re-verify SHA-256 and the fresh-process acceptance.
5. `deploy/deploy-runtime-service.sh` MUST verify `sha256sum` before extracting.

## Regenerate

```bash
python deploy/build_runtime_artifact.py <closure_dir> deploy/artifacts/
```

## Verify

```bash
sha256sum -c deploy/artifacts/zhixue-runtime-v1-phase1gr-p1-student-twin.sha256
```
