"""SECURITY_NETWORK_BACKEND_PERIMETER — the API must be reachable only through nginx.

The backend was started with `--host 0.0.0.0`, so the whole API answered on the public
internet over plain HTTP on :8000, bypassing nginx, TLS, the HTTP→HTTPS redirect, the
security headers and `client_max_body_size`. nginx already proxied to `127.0.0.1:8000`,
so nothing supported depended on the wildcard bind.

These are static guards, not a runtime probe — the deployment that applies the bind is
`.github/workflows/deploy.yml`, which owns the service definition because the base
`ai-backend.service` unit lives on the host and is not in this repository. The runtime
half of the check is the "Guard backend is not publicly reachable" step in that workflow,
which can only be answered from outside the host.

The failure this must catch is a future edit that reintroduces a wildcard bind — in the
workflow, in a service unit, or in the nginx config.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
NGINX_CONFIG = REPO_ROOT / "deploy" / "nginx-ai-study-platform.conf.example"


def _read(path: Path) -> str:
    assert path.is_file(), f"{path} is missing"
    return path.read_text(encoding="utf-8")


def test_no_launch_in_the_deploy_workflow_binds_a_wildcard_host():
    """No executed launch line may carry both `uvicorn` and `0.0.0.0`.

    The workflow is allowed to *mention* the wildcard host — it matches the unit's current
    ExecStart so it can rewrite it, and the surrounding comments explain why — so the check
    is on the launch itself, not on the string. Comments are skipped because they are not
    executed; a commented-out wildcard launch is dead text, not a live bind.
    """
    offenders = [
        f"deploy.yml:{number}: {line.strip()}"
        for number, line in enumerate(_read(DEPLOY_WORKFLOW).splitlines(), 1)
        if not line.strip().startswith("#")
        and "uvicorn" in line
        and "0.0.0.0" in line
    ]
    if offenders:
        pytest.fail("uvicorn is launched on a wildcard host:\n" + "\n".join(offenders))


def test_deploy_workflow_pins_the_backend_to_loopback():
    """The loopback override must exist, and must be applied to the running unit."""
    text = _read(DEPLOY_WORKFLOW)
    assert "loopback-bind.conf" in text, "the loopback bind drop-in is gone"
    assert "--host 127.0.0.1" in text, "the loopback host flag is gone"
    # ExecStart accumulates across drop-ins, so redefining it without clearing it first
    # would append a second process to the unit instead of replacing the wildcard bind.
    assert "ExecStart=\n" in text, "the drop-in must clear ExecStart before redefining it"


def test_deploy_workflow_verifies_the_bind_took_effect():
    """Writing the drop-in is not evidence; the effective unit config is.

    The runtime half has to come from outside the host — from the host, 127.0.0.1 answers
    no matter what the listener binds — so the workflow must carry a public probe too.
    """
    text = _read(DEPLOY_WORKFLOW)
    assert "systemctl show -p ExecStart" in text, "the effective bind is never read back"
    assert "Guard backend is not publicly reachable" in text, "the external guard step is gone"
    assert "/dev/tcp/101.32.190.42/8000" in text, "nothing probes public :8000 from outside"


def test_nginx_proxies_the_backend_only_over_loopback():
    lines = _read(NGINX_CONFIG).splitlines()
    proxies = [line.strip() for line in lines if "proxy_pass" in line]
    assert proxies, "nginx must proxy the backend"
    for line in proxies:
        assert "127.0.0.1:8000" in line, f"nginx proxies the backend off loopback: {line}"
        assert "0.0.0.0" not in line, f"nginx must never proxy to a wildcard host: {line}"


def test_the_internal_health_check_stays_on_loopback():
    """Nothing may reopen public :8000 to make a health check easier."""
    text = _read(DEPLOY_WORKFLOW)
    assert "curl -fsS http://127.0.0.1:8000/health" in text
    assert "http://101.32.190.42:8000" not in text
