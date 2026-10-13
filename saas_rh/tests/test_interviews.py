from fastapi.testclient import TestClient

from saas_rh.main import app

client = TestClient(app)


def test_get_interviews_slots_check_returns_400() -> None:
    response = client.get("/api/interviews/slots")

    assert response.status_code == 422
