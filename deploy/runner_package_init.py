"""Sandbox engine package — installed copy for the sandbox runner.

This file is written to ``/opt/zhixue-sandbox-runner/app/core/sandbox/__init__.py``.

The application's own ``backend/core/sandbox/__init__.py`` is the WEB-SIDE facade. It
imports ``core.code_execution`` (the enablement gate), ``core.config`` and
``core.sandbox.runner_client``, and exposes ``get_execution_backend()`` and
``sandbox_preflight()``.

The runner needs none of that. It IS the backend those functions talk to, and importing the
gate would pull the web application's configuration into the runner's dependency closure —
the opposite of the isolation this split exists to create. That is not hypothetical: with
the facade in place the runner fails at startup with

    ModuleNotFoundError: No module named 'core.code_execution'

because the runner tree deliberately does not carry the web application.

So the install ships the engine (``docker_backend``, ``limits``, ``types``, ``runner.*``)
under a package whose ``__init__`` does nothing. This file lives in the repository rather
than being generated at install time so the divergence from the application copy stays
reviewable.
"""
