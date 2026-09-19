"""Product-side runtime client tests (no real HTTP).

The double sits at the httpx TRANSPORT layer, so request building, timeout handling,
status handling and response parsing all run for real. Transport itself is owned by
``science.client`` — the one Scientific Runtime HTTP client.
"""
import json

import httpx
import pytest

from data_plane import runtime_client


def _client(handler):
    return runtime_client.StudentTwinRuntimeClient(
        base_url="http://127.0.0.1:8101", timeout=1.0,
        transport=httpx.MockTransport(handler))


def _call(fake_post, request):
    """Run one client call through a fake ``post`` delivered via MockTransport."""
    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content or b"{}")
        return fake_post(str(http_request.url), json=body, timeout=None)

    return _client(handler).infer(request)


def _request():
    return {
        "contract_version": 1,
        "request_id": "run-e1",
        "runtime_release_id": "zhixue-runtime-v1-phase1gr-p1",
        "user_ref": "1",
        "target_event_id": "e1",
        "events": [{"event_id": "e1", "occurred_at": 100.0, "activity_type": "PRACTICE", "correct": True}],
    }


def _valid_response(request):
    return {
        "contract_version": 1,
        "request_id": request["request_id"],
        "runtime_release_id": "zhixue-runtime-v1-phase1gr-p1",
        "component_id": "student_twin",
        "scientific_source_class": "ORIGINAL_ARCHIVE_VERIFIED",
        "scientific_source_commit": "a16efa27aac90d9c8d8d9ee703aefe5919f4839e",
        "target_event_id": request["target_event_id"],
        "replayed_events": len(request["events"]),
        "state": {"user_id": "1", "global_ability": 0.5},
        "latency_ms": 1.0,
    }


def _response(status_code, payload):
    return httpx.Response(status_code, json=payload)


def test_runtime_client_success():
    captured = {}
    req = _request()

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _response(200, _valid_response(req))

    resp = _call(fake_post, req)
    assert resp["contract_version"] == 1
    assert resp["state"]["global_ability"] == 0.5
    assert captured["url"].endswith("/v1/inference/student-twin")
    # the canonical request shape is built by the product, not by the test
    assert captured["json"]["runtime_release_id"]


def test_runtime_client_timeout():
    def fake_post(url, json=None, timeout=None):
        raise httpx.ReadTimeout("timed out", request=httpx.Request("POST", url))

    with pytest.raises(runtime_client.RuntimeClientError):
        _call(fake_post, _request())


def test_runtime_client_http_failure():
    def fake_post(url, json=None, timeout=None):
        return httpx.Response(500, text="boom")

    with pytest.raises(runtime_client.RuntimeClientError):
        _call(fake_post, _request())


def test_runtime_client_non_json():
    def fake_post(url, json=None, timeout=None):
        return httpx.Response(200, content=b"<html>")

    with pytest.raises(runtime_client.RuntimeClientError):
        _call(fake_post, _request())


def test_runtime_client_connection_refused_is_bounded():
    def fake_post(url, json=None, timeout=None):
        raise httpx.ConnectError("refused",
                                 request=httpx.Request("POST", url))

    with pytest.raises(runtime_client.RuntimeClientError):
        _call(fake_post, _request())


# --- contract validation: any mismatch must raise, never persist a Prediction ---
def _reject_on(mutate):
    req = _request()

    def fake_post(url, json=None, timeout=None):
        resp = _valid_response(req)
        mutate(resp)
        return _response(200, resp)

    with pytest.raises(runtime_client.RuntimeClientError):
        _call(fake_post, req)


def test_reject_wrong_contract_version():
    _reject_on(lambda r: r.update(contract_version=2))


def test_reject_wrong_request_id():
    _reject_on(lambda r: r.update(request_id="other"))


def test_reject_wrong_runtime_release():
    _reject_on(lambda r: r.update(runtime_release_id="zhixue-runtime-v1-phase1gr"))


def test_reject_wrong_component_id():
    _reject_on(lambda r: r.update(component_id="difficulty_prior"))


def test_reject_wrong_target_event_id():
    _reject_on(lambda r: r.update(target_event_id="e2"))


def test_reject_wrong_replayed_events():
    _reject_on(lambda r: r.update(replayed_events=999))


def test_reject_wrong_source_commit():
    _reject_on(lambda r: r.update(scientific_source_commit="deadbeef"))
