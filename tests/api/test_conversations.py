"""会话 API 和用户数据隔离测试。"""

from fastapi.testclient import TestClient

from tests.conftest import OTHER_USER_ID, OWNER_USER_ID


def test_create_and_get_conversation(seeded_client: TestClient) -> None:
    create_response = seeded_client.post(
        "/api/v1/conversations",
        json={"user_id": OWNER_USER_ID, "title": "物流咨询"},
    )

    assert create_response.status_code == 201
    conversation = create_response.json()["data"]
    assert conversation["user_id"] == OWNER_USER_ID
    assert conversation["status"] == "active"

    get_response = seeded_client.get(
        f"/api/v1/conversations/{conversation['id']}",
        params={"user_id": OWNER_USER_ID},
    )
    assert get_response.status_code == 200
    assert get_response.json()["data"]["title"] == "物流咨询"


def test_other_user_cannot_read_conversation(seeded_client: TestClient) -> None:
    create_response = seeded_client.post(
        "/api/v1/conversations",
        json={"user_id": OWNER_USER_ID, "title": "隐私会话"},
    )
    conversation_id = create_response.json()["data"]["id"]

    response = seeded_client.get(
        f"/api/v1/conversations/{conversation_id}",
        params={"user_id": OTHER_USER_ID},
    )

    # 返回 404 而不是 403，避免向其他用户泄露“这个会话确实存在”。
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_unknown_user_cannot_create_conversation(seeded_client: TestClient) -> None:
    response = seeded_client.post(
        "/api/v1/conversations",
        json={"user_id": "00000000-0000-0000-0000-000000000099"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_new_conversation_has_no_messages(seeded_client: TestClient) -> None:
    create_response = seeded_client.post(
        "/api/v1/conversations",
        json={"user_id": OWNER_USER_ID},
    )
    conversation_id = create_response.json()["data"]["id"]

    response = seeded_client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        params={"user_id": OWNER_USER_ID},
    )

    assert response.status_code == 200
    assert response.json()["data"] == []
