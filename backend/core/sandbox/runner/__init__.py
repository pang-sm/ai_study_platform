"""The sandbox runner service — SECURITY_S0B-P1.

A separate, least-privileged process (OS user ``zhixue-sandbox``) that owns a **rootless**
container runtime (rootless Podman on this host; the argv is built for either runtime by
``core.sandbox.docker_backend``) and is the only component permitted to spawn containers
for learner code.

The web backend (``ai-backend``, OS user ``zhixue-web``) has NO docker binary, NO docker
group and NO rootful socket access. It reaches execution exclusively over a Unix-domain
socket via :mod:`core.sandbox.runner_client`, and the wire schema
(:mod:`core.sandbox.runner.schemas`) accepts only the bounded execution shape — never
argv, image, mounts, environment, host paths or a raw command.
"""
