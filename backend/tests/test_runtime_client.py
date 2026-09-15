"""Product-side runtime client tests (no real HTTP)."""
import httpx
import pytest

from data_plane import runtime_client


def _client():
    return runtime_client.StudentTwinRuntimeClient(base_url="http://127.0.0.1:8101", timeout=1.0)


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
    class _Resp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.text = str(payload)
            self._payload = payload

        def json(self):
            return self._payload

    return _Resp(status_code, payload)


def test_runtime_client_success(monkeypatch):
    captured = {}
    req = _request()

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _response(200, _valid_response(req))

    monkeypatch.setattr(runtime_client.httpx, "post", fake_post)
    resp = _client().infer(req)
    assert resp["contract_version"] == 1
    assert resp["state"]["global_ability"] == 0.5
    assert captured["url"].endswith("/v1/inference/student-twin")


def test_runtime_client_timeout(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(runtime_client.httpx, "post", fake_post)
    with pytest.raises(runtime_client.RuntimeClientError):
        _client().infer(_request())


def test_runtime_client_http_failure(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return _response(500, "boom")

    monkeypatch.setattr(runtime_client.httpx, "post", fake_post)
    with pytest.raises(runtime_client.RuntimeClientError):
        _client().infer(_request())


def test_runtime_client_non_json(monkeypatch):
    class _Bad:
        status_code = 200
        text = "<html>"

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(runtime_client.httpx, "post", lambda url, json=None, timeout=None: _Bad())
    with pytest.raises(runtime_client.RuntimeClientError):
        _client().infer(_request())


# --- contract validation: any mismatch must raise, never persist a Prediction ---
def _reject_on(monkeypatch, mutate):
    req = _request()

    def fake_post(url, json=None, timeout=None):
        resp = _valid_response(req)
        mutate(resp)
        return _response(200, resp)

    monkeypatch.setattr(runtime_client.httpx, "post", fake_post)
    with pytest.raises(runtime_client.RuntimeClientError):
        _client().infer(req)


def test_reject_wrong_contract_version(monkeypatch):
    _reject_on(monkeypatch, lambda r: r.update(contract_version=2))


def test_reject_wrong_request_id(monkeypatch):
    _reject_on(monkeypatch, lambda r: r.update(request_id="other"))


def test_reject_wrong_runtime_release(monkeypatch):
    _reject_on(monkeypatch, lambda r: r.update(runtime_release_id="zhixue-runtime-v1-phase1gr"))


def test_reject_wrong_component_id(monkeypatch):
    _reject_on(monkeypatch, lambda r: r.update(component_id="difficulty_prior"))


def test_reject_wrong_target_event_id(monkeypatch):
    _reject_on(monkeypatch, lambda r: r.update(target_event_id="e2"))


def test_reject_wrong_replayed_events(monkeypatch):
    _reject_on(monkeypatch, lambda r: r.update(replayed_events=999))


def test_reject_wrong_source_commit(monkeypatch):
    _reject_on(monkeypatch, lambda r: r.update(scientific_source_commit="deadbeef"))
