from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def login_admin():
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@smartcollege.com", "password": "Chaadmin123@"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_create_and_current_year_logic():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/academic-years",
        json={"name": "2026-27", "start_date": "2026-06-01", "end_date": "2027-05-31", "is_current": True},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    data = first.json()
    assert data["name"] == "2026-27"
    assert data["is_current"] is True

    second = client.post(
        "/api/academic-years",
        json={"name": "2027-28", "start_date": "2027-06-01", "end_date": "2028-05-31", "is_current": True},
        headers=headers,
    )
    assert second.status_code == 201, second.text
    assert second.json()["is_current"] is True

    listing = client.get("/api/academic-years", headers=headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()
    year_map = {item["name"]: item for item in items}
    assert year_map["2026-27"]["is_current"] is False
    assert year_map["2027-28"]["is_current"] is True


def test_invalid_year_and_duplicate_rejected():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}

    invalid_date = client.post(
        "/api/academic-years",
        json={"name": "2028-29", "start_date": "2028-12-01", "end_date": "2028-06-30", "is_current": False},
        headers=headers,
    )
    assert invalid_date.status_code == 400, invalid_date.text

    duplicate = client.post(
        "/api/academic-years",
        json={"name": "2027-28", "start_date": "2027-06-01", "end_date": "2028-05-31", "is_current": False},
        headers=headers,
    )
    assert duplicate.status_code == 400, duplicate.text
