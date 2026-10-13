from fastapi.testclient import TestClient

from saas_rh.main import app

client = TestClient(app)


def test_post_ask_rag_check_returns_400() -> None:
    response = client.post("/api/rag/ask")

    assert response.status_code == 400
