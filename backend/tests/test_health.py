"""Prueba de humo del healthcheck del scaffold."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    """El endpoint de salud responde 200 con estado ok."""
    # Given / When
    response = client.get("/api/v1/health")
    # Then
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
