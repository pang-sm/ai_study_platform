"""Product-side runtime client tests (no real HTTP)."""
import httpx
import pytest

from data_plane import runtime_client


def _client():
    return runtime_client.StudentTwinRuntimeClient(base_url="http://127.0.0.1:8101", timeout=1.0)


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

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _response(200, {"contract_version": 1, "state": {"user_id": "1", "global_ability": 0.5}})

    monkeypatch.setattr(runtime_client.httpx, "post", fake_post)
    resp = _client().infer({"contract_version": 1})
    assert resp["contract_version"] == 1
    assert captured["url"].endswith("/v1/inference/student-twin")


def test_runtime_client_timeout(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(runtime_client.httpx, "post", fake_post)
    with pytest.raises(runtime_client.RuntimeClientError):
        _client().infer({"contract_version": 1})


def test_runtime_client_http_failure(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return _response(500, "boom")

    monkeypatch.setattr(runtime_client.httpx, "post", fake_post)
    with pytest.raises(runtime_client.RuntimeClientError):
        _client().infer({"contract_version": 1})


def test_runtime_client_invalid_contract(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return _response(200, {"contract_version": 2, "state": {}})

    monkeypatch.setattr(runtime_client.httpx, "post", fake_post)
    with pytest.raises(runtime_client.RuntimeClientError):
        _client().infer({"contract_version": 1})


def test_runtime_client_non_json(monkeypatch):
    class _Bad:
        status_code = 200
        text = "<html>"

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(runtime_client.httpx, "post", lambda url, json=None, timeout=None: _Bad())
    with pytest.raises(runtime_client.RuntimeClientError):
        _client().infer({"contract_version": 1})
