"""阶段 3 基础聊天闭环的最小验证。"""

from fastapi.testclient import TestClient

from tests.conftest import OWNER_USER_ID


def test_chat_creates_conversation_and_persists_both_messages(
    seeded_client: TestClient,
) -> None:
    response = seeded_client.post(
        "/api/v1/chat",
        json={"user_id": OWNER_USER_ID, "message": "我的订单什么时候发货？"},
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["model"] == "mock-customer-service"
    assert "我的订单什么时候发货" in result["answer"]

    messages_response = seeded_client.get(
        f"/api/v1/conversations/{result['conversation_id']}/messages",
        params={"user_id": OWNER_USER_ID},
    )
    messages = messages_response.json()["data"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "我的订单什么时候发货？"
    assert messages[1]["metadata"]["model"] == "mock-customer-service"
