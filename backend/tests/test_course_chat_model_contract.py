from schemas import ChatRequest


def test_chat_request_accepts_null_model_id_as_auto_selection():
    request = ChatRequest(message="解释链表", model_id=None)

    assert request.model_id is None
