"""SECURITY_S0.5 — the retired ADMIN_LOGIN_CODE must stay retired.

It was provisioned into a world-readable systemd drop-in on every deploy while having no
reader anywhere in the backend: no admin login path consulted it. That combination is pure
liability — a credential-shaped value on disk that buys nothing and widens the blast radius
of any local read primitive (which is exactly what SECURITY_S0 closed).

This test is static on purpose. The failure it guards against is someone re-introducing the
variable because it *looks* like it must gate admin access; asserting on the source is the
only way to catch that before it reaches a host.
"""
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

RETIRED_SECRET = "ADMIN_LOGIN_CODE"


def _production_sources() -> list[Path]:
    """Shipped modules only — the tests themselves are allowed to name the retired key."""
    return [
        path for path in BACKEND_ROOT.rglob("*.py")
        if ".venv" not in path.parts
        and "__pycache__" not in path.parts
        and "tests" not in path.relative_to(BACKEND_ROOT).parts
    ]


def test_no_backend_python_module_reads_the_retired_secret():
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _production_sources()
        if RETIRED_SECRET in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert offenders == [], (
        "ADMIN_LOGIN_CODE was retired because nothing read it; these modules now reference it: "
        f"{offenders}"
    )


def test_deploy_workflow_no_longer_provisions_the_retired_secret():
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    # Prose explaining the retirement is fine; a live reference is not.
    live_lines = [
        line.strip() for line in workflow.splitlines()
        if RETIRED_SECRET in line and not line.strip().startswith("#")
    ]
    assert live_lines == [], f"deploy.yml still provisions the retired secret: {live_lines}"


def test_deploy_workflow_retires_any_stale_drop_in_on_the_host():
    """Removing the injection is not enough: an earlier deploy already wrote the file."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert "admin-code.conf" in workflow, "expected an explicit cleanup of the stale drop-in"
    assert "rm -f /etc/systemd/system/ai-backend.service.d/admin-code.conf" in workflow


def test_smtp_secret_drop_in_is_forced_to_owner_only_mode():
    """A password-bearing drop-in must not inherit the deploy umask (typically 0644)."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert "chmod 600 /etc/systemd/system/ai-backend.service.d/smtp.conf" in workflow
