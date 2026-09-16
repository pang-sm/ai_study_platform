"""STEP 7C-P: GET /ai/models — user-facing qualified model options."""
from conftest import register_and_login


def test_ai_models_free_basic_only(client):
    register_and_login(client, "aim_1")
    r = client.get("/ai/models?capability=tutor.chat")
    assert r.status_code == 200
    body = r.json()
    assert body["default"] == "auto"
    assert body["tier"] == "free"
    models = {o["model"] for o in body["options"]}
    assert "qwen3.8-flash" in models
    assert "glm-5.3-flash" in models       # cross-provider fallback
    assert "deepseek-flash" in models
    assert "deepseek-v4-pro" not in models  # premium hidden from Free


def test_ai_models_unknown_capability_400(client):
    register_and_login(client, "aim_2")
    r = client.get("/ai/models?capability=bogus.cap")
    assert r.status_code == 400


def test_ai_models_advanced_sees_premium(client):
    register_and_login(client, "aim_3")
    order = client.post("/subscription/orders", json={"tier": "advanced", "duration_days": 30}).json()["order"]
    client.post(f"/subscription/orders/{order['id']}/pay")
    r = client.get("/ai/models?capability=programming.debug")
    assert r.status_code == 200
    assert r.json()["tier"] == "advanced"
    models = {o["model"] for o in r.json()["options"]}
    assert "deepseek-v4-pro" in models


def test_ai_models_free_denied_premium_capability(client):
    register_and_login(client, "aim_5")
    # free tier is not entitled to question.generate → 403, no model leak
    r = client.get("/ai/models?capability=question.generate")
    assert r.status_code == 403


def test_ai_models_no_full_registry(client):
    register_and_login(client, "aim_4")
    # Free tier must NOT leak standard+/advanced-only models
    r = client.get("/ai/models?capability=tutor.chat")
    options = r.json()["options"]
    models = {o["model"] for o in options}
    assert "qwen3.8-max" not in models              # standard-only
    assert "MiniMax-M2.7-highspeed" not in models   # standard-only
    assert "MiniMax-M3" not in models               # advanced-only
    assert "deepseek-v4-pro" not in models          # advanced-only
