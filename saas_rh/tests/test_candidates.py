from fastapi.testclient import TestClient

from saas_rh.main import app

client = TestClient(app)


def test_post_parse_candidate_check_returns_400() -> None:
    response = client.post("/api/candidates/parse")

    assert response.status_code == 400
