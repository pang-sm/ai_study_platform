from types import SimpleNamespace

import main
import models


def test_provider_reported_usage_is_saved_without_prompt_content(db_session, monkeypatch):
    user = models.User(username="meter_user", hashed_password="x")
    db_session.add(user)
    db_session.commit()

    response = SimpleNamespace(
        model="deepseek-v4-flash",
        id="provider-request-test",
        _request_id="provider-request-test",
        usage=SimpleNamespace(
            prompt_tokens=120, completion_tokens=45, total_tokens=165,
            prompt_tokens_details=SimpleNamespace(cached_tokens=20),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=0),
        ),
        choices=[SimpleNamespace(message=SimpleNamespace(content="答案"))],
    )
    monkeypatch.setattr(main.client.chat.completions, "create", lambda **_: response)

    answer = main.call_deepseek([{"role": "user", "content": "不应写入日志"}])
    assert answer == "答案"
    main.record_ai_usage("meter_user", "chat", db_session, service_key="course_learning")

    row = db_session.query(models.AiUsageLog).filter(models.AiUsageLog.username == "meter_user").one()
    assert row.provider == "deepseek"
    assert row.requested_model == "deepseek-chat"
    assert row.resolved_model == "deepseek-v4-flash"
    assert (row.input_tokens, row.output_tokens, row.cached_input_tokens, row.total_tokens) == (120, 45, 20, 165)
    assert row.usage_source == "PROVIDER_REPORTED"
    assert row.provider_request_id == "provider-request-test"
    assert row.estimated_api_cost is not None
    assert "不应写入日志" not in str(row.__dict__)


def test_cached_input_is_not_double_charged_and_is_clamped():
    no_cache = main._deepseek_v4_flash_cost_cny(100, 50, 0)
    partial_cache = main._deepseek_v4_flash_cost_cny(100, 50, 40)
    full_cache = main._deepseek_v4_flash_cost_cny(100, 50, 100)
    invalid_cache = main._deepseek_v4_flash_cost_cny(100, 50, 999)
    assert full_cache < partial_cache < no_cache
    assert invalid_cache == full_cache


def test_two_provider_requests_share_one_action_but_remain_two_rows(db_session, monkeypatch):
    user = models.User(username="action_meter_user", hashed_password="x")
    db_session.add(user); db_session.commit()
    token = main._ai_usage_action_id.set("one-user-action")
    for request_id in ("provider-1", "provider-2"):
        response = SimpleNamespace(model="deepseek-v4-flash", id=request_id, _request_id=request_id,
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0), completion_tokens_details=SimpleNamespace(reasoning_tokens=3)),
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])
        monkeypatch.setattr(main.client.chat.completions, "create", lambda *args, _response=response, **kwargs: _response)
        main.call_deepseek([{"role": "user", "content": "x"}])
        main.record_ai_usage(user.username, "json_repair", db_session, service_key="programming")
    rows = db_session.query(models.AiUsageLog).filter(models.AiUsageLog.username == user.username).all()
    main._ai_usage_action_id.reset(token)
    assert len(rows) == 2 and {row.action_id for row in rows} == {"one-user-action"}
    assert all(row.reasoning_tokens == 3 for row in rows)  # reported separately; not added to output cost
