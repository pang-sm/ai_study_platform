"""The ONE HTTP client for the Scientific Runtime Service.

Design constraints this module exists to satisfy:

* **Bounded.** Every call has a wall-clock timeout. There is no unbounded wait, no retry
  storm, and no streaming — a scientific preview may be slow, but it may not hang a
  product request.
* **Correlated.** A ``request_id`` is generated (or propagated) per call and sent to the
  runtime, so one product action can be traced across the process boundary.
* **Bounded failure.** Transport/timeout/5xx/malformed-body all collapse into
  ``ScientificUnavailable``; a 4xx (our request was wrong) into ``ScientificRejected``.
  Callers translate those into an explicit "temporarily unavailable" answer. A scientific
  outage must never become an unhandled 500 in a core learning flow.
* **Heavy-import free.** This module imports ``httpx`` and nothing scientific. The runtime
  owns the models.
"""
from __future__ import annotations

import logging
import uuid

import httpx

from core.config import scientific_runtime_base_url, scientific_runtime_timeout

logger = logging.getLogger("science.client")

# A preview must not be able to hold a product request open indefinitely. The client
# timeout comes from config (SCIENTIFIC_RUNTIME_TIMEOUT, default 10s) and applies to the
# whole request, not just the connect.
MAX_RESPONSE_BYTES = 2_000_000


class ScientificRuntimeError(Exception):
    """Base class for every scientific-boundary failure."""

    def __init__(self, message: str, *, component: str | None = None,
                 request_id: str | None = None, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.component = component
        self.request_id = request_id
        self.detail = detail


class ScientificUnavailable(ScientificRuntimeError):
    """The runtime could not be reached, timed out, errored, or answered nonsense.

    This is the bounded "temporarily unavailable" case. It is NEVER a learner-visible
    error state, and it never means the product is broken.
    """


class ScientificRejected(ScientificRuntimeError):
    """The runtime rejected our request (4xx). A product-side contract bug, not an outage."""


def new_request_id(component: str) -> str:
    """A correlation id for one scientific call, unique per request."""
    return f"sci-{component}-{uuid.uuid4().hex[:16]}"


class ScientificClient:
    """Typed, bounded HTTP access to the Scientific Runtime Service."""

    def __init__(self, *, base_url: str | None = None, timeout: float | None = None,
                 transport: httpx.BaseTransport | None = None):
        self._base_url = (base_url or scientific_runtime_base_url()).rstrip("/")
        self._timeout = float(timeout if timeout is not None else scientific_runtime_timeout())
        # ``transport`` is the seam a test uses to stand in BELOW the HTTP boundary.
        # It is never set in production.
        self._transport = transport

    @property
    def base_url(self) -> str:
        return self._base_url

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base_url, timeout=self._timeout,
                            transport=self._transport)

    def _request(self, method: str, path: str, *, component: str,
                 json_body: dict | None = None) -> dict:
        request_id = (json_body or {}).get("request_id")
        try:
            with self._client() as client:
                response = client.request(method, path, json=json_body)
        except httpx.TimeoutException as exc:
            raise ScientificUnavailable(
                "scientific runtime timed out", component=component,
                request_id=request_id, detail=f"timeout after {self._timeout}s") from exc
        except httpx.HTTPError as exc:
            raise ScientificUnavailable(
                "scientific runtime unreachable", component=component,
                request_id=request_id, detail=type(exc).__name__) from exc

        if response.status_code >= 500:
            raise ScientificUnavailable(
                "scientific runtime error", component=component, request_id=request_id,
                detail=f"HTTP {response.status_code}")
        if response.status_code >= 400:
            raise ScientificRejected(
                "scientific runtime rejected the request", component=component,
                request_id=request_id,
                detail=f"HTTP {response.status_code}: {response.text[:300]}")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ScientificUnavailable(
                "scientific runtime response too large", component=component,
                request_id=request_id)
        try:
            body = response.json()
        except ValueError as exc:
            raise ScientificUnavailable(
                "scientific runtime returned a non-JSON body", component=component,
                request_id=request_id) from exc
        if not isinstance(body, dict):
            raise ScientificUnavailable(
                "scientific runtime returned an unexpected body shape",
                component=component, request_id=request_id)
        return body

    # ------------------------------------------------------------------ surface

    def health(self, *, timeout: float | None = None) -> dict:
        """Bounded liveness probe. Never raises for a down runtime."""
        try:
            with httpx.Client(base_url=self._base_url,
                              timeout=timeout if timeout is not None else 2.0,
                              transport=self._transport) as client:
                response = client.get("/health")
            if response.status_code != 200:
                return {"status": "unavailable", "reason": f"HTTP {response.status_code}"}
            return response.json()
        except httpx.HTTPError as exc:
            return {"status": "unavailable", "reason": type(exc).__name__}

    def infer(self, path: str, payload: dict, *, component: str) -> dict:
        """POST one typed inference request. Raises ScientificUnavailable/Rejected."""
        return self._request("POST", path, component=component, json_body=payload)


_default_client: ScientificClient | None = None


def get_client() -> ScientificClient:
    """The process-wide client. Configuration is read once per process."""
    global _default_client
    if _default_client is None:
        _default_client = ScientificClient()
    return _default_client


def reset_client() -> None:
    """Drop the cached client (used when configuration is reloaded, and by tests)."""
    global _default_client
    _default_client = None
