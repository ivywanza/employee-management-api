
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_register_employee():
    response = client.post(
        "/users/",
        json={
            "full_name": "John Doe",
            "email": "john.doe@example.com",
            "phone_number": "+254712345678",
            "organisation": "red_ant",
            "role": "employee"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "john.doe@example.com"
    assert data["full_name"] == "John Doe"
    assert data["role"] == "employee"
