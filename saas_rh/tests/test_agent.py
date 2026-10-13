from fastapi.testclient import TestClient

from saas_rh.main import app

client = TestClient(app)


def test_post_agent_chat_returns_sse_event() -> None:
    with client.stream("POST", "/api/agent/chat") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "data: Route SSE prête" in response.read().decode()
