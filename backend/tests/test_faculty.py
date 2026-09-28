import uuid

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


def create_department(headers, suffix):
    response = client.post(
        "/api/departments",
        json={"name": f"Department {suffix}", "code": f"D{suffix}", "description": "Dept"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def faculty_payload(suffix, department_id, **overrides):
    payload = {
        "faculty_id": f"FAC{suffix}",
        "department_id": department_id,
        "first_name": "Rahul",
        "last_name": "Kumar",
        "email": f"rahul.{suffix}@college.edu",
        "phone": "9876543210",
        "designation": "Assistant Professor",
        "qualification": "M.Tech",
        "joining_date": "2026-07-01",
        "employee_type": "Full Time",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def test_create_faculty_creates_user_and_faculty_records():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    department_id = create_department(headers, suffix)

    response = client.post("/api/faculty", json=faculty_payload(suffix, department_id), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["faculty_id"] == f"FAC{suffix}".upper()
    assert body["full_name"] == "Rahul Kumar"
    assert body["department_id"] == department_id
    assert body["user_id"] > 0
    # the generated password is handed back exactly once, at creation
    assert body["generated_password"]

    login = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["role"] == "FACULTY"


def test_duplicate_faculty_id_and_email_are_rejected():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    department_id = create_department(headers, suffix)

    first = client.post("/api/faculty", json=faculty_payload(suffix, department_id), headers=headers)
    assert first.status_code == 201, first.text

    duplicate_id = client.post(
        "/api/faculty",
        json=faculty_payload(suffix, department_id, email=f"other.{suffix}@college.edu"),
        headers=headers,
    )
    assert duplicate_id.status_code == 400, duplicate_id.text

    duplicate_email = client.post(
        "/api/faculty",
        json=faculty_payload(suffix, department_id, faculty_id=f"FACX{suffix}"),
        headers=headers,
    )
    assert duplicate_email.status_code == 400, duplicate_email.text


def test_faculty_field_validation():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    department_id = create_department(headers, suffix)

    missing_department = client.post(
        "/api/faculty",
        json=faculty_payload(suffix, 999999),
        headers=headers,
    )
    assert missing_department.status_code == 404, missing_department.text

    invalid_email = client.post(
        "/api/faculty",
        json=faculty_payload(suffix, department_id, email="not-an-email"),
        headers=headers,
    )
    assert invalid_email.status_code == 400, invalid_email.text

    invalid_phone = client.post(
        "/api/faculty",
        json=faculty_payload(suffix, department_id, phone="123"),
        headers=headers,
    )
    assert invalid_phone.status_code in (400, 422), invalid_phone.text

    invalid_designation = client.post(
        "/api/faculty",
        json=faculty_payload(suffix, department_id, designation="Chief Wizard"),
        headers=headers,
    )
    assert invalid_designation.status_code == 400, invalid_designation.text

    invalid_employee_type = client.post(
        "/api/faculty",
        json=faculty_payload(suffix, department_id, employee_type="Whenever"),
        headers=headers,
    )
    assert invalid_employee_type.status_code == 400, invalid_employee_type.text


def test_search_and_department_filter():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    department_id = create_department(headers, suffix)
    other_department_id = create_department(headers, other_suffix)

    created = client.post(
        "/api/faculty",
        json=faculty_payload(suffix, department_id, first_name="Priya"),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    faculty_pk = created.json()["id"]

    searched = client.get("/api/faculty", params={"search": "priya"}, headers=headers)
    assert searched.status_code == 200, searched.text
    assert any(item["id"] == faculty_pk for item in searched.json())

    filtered = client.get("/api/faculty", params={"department_id": department_id}, headers=headers)
    assert filtered.status_code == 200, filtered.text
    assert all(item["department_id"] == department_id for item in filtered.json())

    excluded = client.get("/api/faculty", params={"department_id": other_department_id}, headers=headers)
    assert excluded.status_code == 200, excluded.text
    assert all(item["id"] != faculty_pk for item in excluded.json())


def test_deactivated_faculty_cannot_log_in():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    department_id = create_department(headers, suffix)

    created = client.post("/api/faculty", json=faculty_payload(suffix, department_id), headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()

    deactivated = client.patch(f"/api/faculty/{body['id']}/status", json={"is_active": False}, headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False

    blocked = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert blocked.status_code == 401, blocked.text

    reactivated = client.patch(f"/api/faculty/{body['id']}/status", json={"is_active": True}, headers=headers)
    assert reactivated.status_code == 200, reactivated.text

    allowed = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert allowed.status_code == 200, allowed.text


def test_faculty_role_cannot_reach_admin_endpoints():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    department_id = create_department(headers, suffix)

    created = client.post("/api/faculty", json=faculty_payload(suffix, department_id), headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()

    login = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert login.status_code == 200, login.text
    faculty_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/faculty", headers=faculty_headers).status_code == 403
    assert client.get("/api/departments", headers=faculty_headers).status_code == 403
    assert client.post(
        "/api/faculty",
        json=faculty_payload(uuid.uuid4().hex[:6], department_id),
        headers=faculty_headers,
    ).status_code == 403

    profile = client.get("/api/faculty/me/profile", headers=faculty_headers)
    assert profile.status_code == 200, profile.text
    assert profile.json()["faculty_id"] == body["faculty_id"]

    updated = client.put(
        "/api/faculty/me/profile",
        json={"first_name": "Rahul", "last_name": "Kumar", "phone": "9876500000", "qualification": "Ph.D"},
        headers=faculty_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["qualification"] == "Ph.D"
