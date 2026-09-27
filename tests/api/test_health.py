"""健康检查与请求 Trace 的接口测试。"""

from fastapi.testclient import TestClient

from aidahelp.api.dependencies import get_database


def test_liveness_returns_standard_response(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["environment"] == "testing"
    assert body["data"]["checks"] == {"application": "ok"}
    # 响应体和响应头必须使用同一个 trace_id，方便用户报错后快速定位日志。
    assert body["trace_id"] == response.headers["X-Trace-ID"]


def test_safe_client_trace_id_is_reused(client: TestClient) -> None:
    trace_id = "client-trace-0001"
    response = client.get(
        "/api/v1/health/ready",
        headers={"X-Trace-ID": trace_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == trace_id
    assert response.json()["trace_id"] == trace_id


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["data"]["checks"] == {
        "application": "ok",
        "mysql": "ok",
    }


def test_readiness_returns_503_when_database_is_unavailable(client: TestClient) -> None:
    class UnavailableDatabase:
        async def ping(self) -> bool:
            return False

    client.app.dependency_overrides[get_database] = lambda: UnavailableDatabase()
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"]["status"] == "not_ready"
    assert body["data"]["checks"]["mysql"] == "error"
    assert body["error"]["code"] == "DATABASE_NOT_READY"


def test_unsafe_trace_id_is_replaced(client: TestClient) -> None:
    # 长度过短，不符合服务允许的 trace_id 规则，应由服务生成新的值。
    response = client.get(
        "/api/v1/health/live",
        headers={"X-Trace-ID": "short"},
    )

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] != "short"


def test_not_found_uses_standard_error_response(client: TestClient) -> None:
    response = client.get("/api/v1/not-exists")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HTTP_404"
    assert body["trace_id"] == response.headers["X-Trace-ID"]
