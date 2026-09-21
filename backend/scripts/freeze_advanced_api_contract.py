"""P6 §H — freeze the advanced-capability API surface for the competition release.

WHAT IT DOES
------------
Reads the FastAPI application's OWN route table and writes a snapshot of exactly the frozen
paths, so the snapshot cannot drift from the code it describes:

    THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_API_CONTRACT_FREEZE.json   (machine-readable)
    THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_API_CONTRACT_FREEZE.md     (human-readable)

This is NOT a second OpenAPI document. It is a drift DETECTOR: each entry carries a short
fingerprint of the contract shape (method, path, parameters, response model name, the first
line of the handler's docstring). Re-running the script after a frontend or deployment phase
shows exactly which frozen entries moved, and nothing else.

USAGE
-----
    cd backend && ./.venv/Scripts/python.exe scripts/freeze_advanced_api_contract.py
    (any platform: python scripts/freeze_advanced_api_contract.py)

It writes files at the repository root and never touches the database.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import os  # noqa: E402
import tempfile  # noqa: E402

# Importing the app runs its schema bootstrap, so it must land in a throwaway directory: the
# real backend/app.db is never opened, and `DATABASE_URL` is only defaulted (never overridden)
# so an explicit value from the caller still wins.
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="p6-freeze-"))
os.environ.setdefault("DATABASE_URL", "sqlite:///" + (_TMP_ROOT / "freeze.db").as_posix())
os.environ.setdefault("UPLOAD_ROOT", str(_TMP_ROOT / "uploads"))

# (method, path) — the frozen surface. Order is the reading order of the freeze document.
FROZEN_SURFACE: list[tuple[str, str]] = [
    ("POST", "/ai/deep-study"),
    ("POST", "/programming/agent/debug"),
    ("POST", "/ai/learning-report"),
    ("POST", "/wrong-answers/{state_id}/analysis"),
    ("POST", "/ai/plan-adjustment"),
    ("POST", "/ai/plan-adjustment/apply"),
    ("GET", "/adaptive/practice"),
    ("POST", "/ai/feedback"),
    ("GET", "/ai/feedback/analytics"),
    ("GET", "/ai/feedback/availability"),
    ("GET", "/review"),
    ("GET", "/review/summary"),
    ("POST", "/review/schedule"),
    ("POST", "/review/{item_id}/complete"),
    ("GET", "/learning/agenda"),
    ("GET", "/learning/agenda/explain"),
    ("GET", "/admin/ai-operations/summary"),
    ("GET", "/admin/workflow-operations/summary"),
    ("GET", "/admin/workflow-operations/agent-runs/{run_id}"),
    ("GET", "/admin/feature-flags"),
    ("PUT", "/admin/feature-flags"),
]

# What each path FREEZES — a one-line intent, so a reader knows what breaking it costs.
INTENT: dict[tuple[str, str], str] = {
    ("POST", "/ai/deep-study"): "grounded strong-reasoning answer + citations + usage",
    ("POST", "/programming/agent/debug"): "bounded debug run: code-free step trace + verdict",
    ("POST", "/ai/learning-report"): "deterministic report + optional AI narrative",
    ("POST", "/wrong-answers/{state_id}/analysis"): "facts / AI reading, explicitly separated",
    ("POST", "/ai/plan-adjustment"): "plan adjustment PROPOSAL (writes nothing)",
    ("POST", "/ai/plan-adjustment/apply"): "apply an accepted proposal (stale → 409)",
    ("GET", "/adaptive/practice"): "next-practice candidates, each with its factual reason",
    ("POST", "/ai/feedback"): "rate one of the caller's own AI responses",
    ("GET", "/ai/feedback/analytics"): "mine | admin-only platform aggregate of ratings",
    ("GET", "/ai/feedback/availability"): "router availability WITH its process-local scope",
    ("GET", "/review"): "outstanding review work (due / needs_attention / scheduled)",
    ("GET", "/review/summary"): "counts over the SAME projection the list serves",
    ("POST", "/review/schedule"): "record the next review date from stored facts",
    ("POST", "/review/{item_id}/complete"): "record a real review result and reschedule",
    ("GET", "/learning/agenda"): "the daily learning agenda projection",
    ("GET", "/learning/agenda/explain"): "why an agenda entry is where it is",
    ("GET", "/admin/ai-operations/summary"): "admin-only AI accounting aggregate",
    ("GET", "/admin/workflow-operations/summary"): "admin-only per-workflow aggregate",
    ("GET", "/admin/workflow-operations/agent-runs/{run_id}"): "admin-only run trace (code-free)",
    ("GET", "/admin/feature-flags"): "the seven advanced-workflow kill switches",
    ("PUT", "/admin/feature-flags"): "set a flag mode (OFF/INTERNAL/TIER/ALL)",
}


def _ref_name(schema: dict | None) -> str:
    """The declared model name of a schema, or its JSON type / payload shape."""
    schema = schema or {}
    ref = schema.get("$ref")
    if ref:
        return ref.rsplit("/", 1)[-1]
    if "$anyOf" in schema:
        return "|".join(_ref_name(part) for part in schema["$anyOf"])
    if "items" in schema:
        return f"list[{_ref_name(schema['items'])}]"
    return schema.get("type", "inline")


def _field_names(schemas: dict, model_name: str) -> list[str]:
    """Top-level field names of a declared model — what a request/response actually carries."""
    model = schemas.get(model_name)
    if not isinstance(model, dict):
        return []
    properties = model.get("properties")
    return sorted(properties) if isinstance(properties, dict) else []


def _summary_line(operation: dict) -> str:
    """The handler's first docstring line — the operation's own one-line contract."""
    text = str(operation.get("summary") or operation.get("description") or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else ""


def _fingerprint(entry: dict) -> str:
    material = json.dumps({k: entry[k] for k in
                           ("method", "path", "parameters", "request_model", "request_fields",
                            "response_model", "response_fields")},
                          sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def collect() -> dict:
    """Read the app's OWN OpenAPI schema — the public, stable view of every frozen route."""
    import main  # noqa: WPS433 — intentional: the app IS the source of truth

    schema = main.app.openapi()
    paths = schema.get("paths", {})
    schemas = (schema.get("components", {}) or {}).get("schemas", {}) or {}

    entries = []
    missing = []
    for method, path in FROZEN_SURFACE:
        operation = (paths.get(path) or {}).get(method.lower())
        if operation is None:
            missing.append(f"{method} {path}")
            continue
        parameters = sorted(
            f"{item['name']}:{item['in']}{'' if item.get('required') else '?'}"
            for item in operation.get("parameters", []))
        body = (operation.get("requestBody", {}) or {}).get("content", {}) or {}
        request_model = _ref_name((body.get("application/json") or {}).get("schema"))
        responses = operation.get("responses", {}) or {}
        success = responses.get("200") or responses.get("201") or {}
        response_schema = ((success.get("content") or {})
                           .get("application/json", {}) or {}).get("schema")
        response_model = _ref_name(response_schema)
        entry = {
            "method": method,
            "path": path,
            "handler": operation.get("operationId", ""),
            "parameters": parameters,
            "request_model": request_model,
            "request_fields": _field_names(schemas, request_model),
            "response_model": response_model,
            "response_fields": _field_names(schemas, response_model),
            "intent": INTENT.get((method, path), ""),
            "summary": _summary_line(operation),
        }
        entry["fingerprint"] = _fingerprint(entry)
        entries.append(entry)

    return {
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "phase": "THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6",
        "purpose": ("drift detection for the advanced-capability API surface after the freeze; "
                    "regenerate and diff — a changed fingerprint is a contract change"),
        "count": len(entries),
        "missing": missing,
        "entries": entries,
        "surface_fingerprint": hashlib.sha256(
            json.dumps([e["fingerprint"] for e in entries], sort_keys=True).encode("utf-8")
        ).hexdigest()[:16],
    }


def render_markdown(snapshot: dict) -> str:
    lines = [
        "# P6 API CONTRACT FREEZE — advanced capabilities",
        "",
        f"Generated: `{snapshot['generated_at']}` · entries: **{snapshot['count']}** · "
        f"surface fingerprint: `{snapshot['surface_fingerprint']}`",
        "",
        "> Drift detector, not an OpenAPI copy. A changed fingerprint is a contract change and "
        "must be a deliberate, reviewed decision — never a side effect of a frontend or "
        "deployment change.",
        "",
        "| # | Method | Path | Request | Response | Fingerprint |",
        "|---|--------|------|---------|----------|-------------|",
    ]
    for index, entry in enumerate(snapshot["entries"], start=1):
        lines.append(f"| {index} | `{entry['method']}` | `{entry['path']}` | "
                     f"`{entry['request_model']}` | `{entry['response_model']}` | "
                     f"`{entry['fingerprint']}` |")
    lines += ["", "## Frozen intent per entry", ""]
    for entry in snapshot["entries"]:
        lines.append(f"### `{entry['method']} {entry['path']}`")
        lines.append("")
        lines.append(f"- handler: `{entry['handler']}`")
        lines.append(f"- request model: `{entry['request_model']}`")
        if entry["request_fields"]:
            lines.append(f"- request fields: "
                         f"{', '.join('`'+f+'`' for f in entry['request_fields'])}")
        lines.append(f"- response model: `{entry['response_model']}`")
        if entry["response_fields"]:
            lines.append(f"- response fields: "
                         f"{', '.join('`'+f+'`' for f in entry['response_fields'])}")
        lines.append(f"- parameters: {', '.join('`'+p+'`' for p in entry['parameters']) or '—'}")
        if entry["intent"]:
            lines.append(f"- frozen intent: {entry['intent']}")
        if entry["summary"]:
            lines.append(f"- contract: {entry['summary']}")
        lines.append("")
    if snapshot["missing"]:
        lines += ["## NOT FOUND (a frozen path disappeared)", ""]
        lines += [f"- `{item}`" for item in snapshot["missing"]]
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    snapshot = collect()
    json_path = REPO_ROOT / "THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_API_CONTRACT_FREEZE.json"
    md_path = REPO_ROOT / "THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_API_CONTRACT_FREEZE.md"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(snapshot), encoding="utf-8")
    print(f"entries={snapshot['count']} surface={snapshot['surface_fingerprint']} "
          f"missing={len(snapshot['missing'])}")
    for item in snapshot["missing"]:
        print(f"MISSING {item}")
    return 1 if snapshot["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
