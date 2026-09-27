"""The error body is a learner-facing surface, and the only thing allowed in it is a sentence.

WHY THIS EXISTS
---------------
`POST /chat` on a machine with no usable provider credential answered 500 with

    服务器内部错误，请稍后重试。详情：Missing credentials. Please pass an `api_key`, ... or set
    the `OPENAI_API_KEY` ... environment variable.

The first half is for the learner. The second half named the provider's SDK, the environment
variable it wanted, and — through the provider behind it — which vendor answers a question. A
learner can act on none of that, and the product's own rule (STEP7H handoff §I.5) says the
provider registry is not theirs to read.

The fix is not in the UI: it is that the detail was ever put in the body. The exception is
already logged with a stack trace, which is where a debugging aid belongs, so the handler now
returns the sentence and nothing else.

Both handlers are covered — a 422's `exc.errors()` names request FIELDS, which is the same
mistake in a quieter form.
"""
from __future__ import annotations

import asyncio

import pytest


class _StubRequest:
    """Only what the handlers read. They log the method and path, nothing else."""

    class _URL:
        path = "/chat"

    method = "POST"
    url = _URL()


def _body(response) -> str:
    import json

    return json.dumps(json.loads(response.body.decode("utf-8")), ensure_ascii=False)


def test_a_500_body_carries_a_sentence_and_no_provider_internals():
    import main

    leaked = (
        "Missing credentials. Please pass an `api_key`, `workload_identity`, "
        "`admin_api_key`, or set the `OPENAI_API_KEY` environment variable."
    )
    response = asyncio.run(main.global_exception_json_handler(_StubRequest(), RuntimeError(leaked)))

    assert response.status_code == 500
    body = _body(response)
    assert "服务器内部错误" in body
    for forbidden in ("OPENAI_API_KEY", "api_key", "credentials", "详情", "RuntimeError"):
        assert forbidden not in body, f"the 500 body leaked {forbidden!r}"


def test_a_422_body_does_not_name_the_request_fields():
    import main
    from fastapi.exceptions import RequestValidationError

    exc = RequestValidationError(
        [{"type": "missing", "loc": ("body", "model_preference"), "msg": "Field required"}]
    )
    response = asyncio.run(main.validation_exception_json_handler(_StubRequest(), exc))

    assert response.status_code == 422
    body = _body(response)
    assert "请求参数校验失败" in body
    for forbidden in ("model_preference", "Field required", "loc", "body"):
        assert forbidden not in body, f"the 422 body leaked {forbidden!r}"


def test_the_provider_name_never_reaches_an_ai_error_body():
    """The AI boundary answers with its own words (§F), not with the SDK's."""
    import main

    for exc in (
        RuntimeError("Connection error to https://api.deepseek.com/v1/chat/completions"),
        RuntimeError("qwen: insufficient quota for model qwen3.8-max"),
    ):
        body = _body(asyncio.run(main.global_exception_json_handler(_StubRequest(), exc)))
        for forbidden in ("deepseek", "qwen", "api.", "http"):
            assert forbidden not in body.lower(), f"the 500 body leaked {forbidden!r}"
