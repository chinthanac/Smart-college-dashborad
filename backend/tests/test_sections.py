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


def test_create_section_success_and_duplicate_rejected():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]

    department = client.post(
        "/api/departments",
        json={"name": f"Department {suffix}", "code": f"D{suffix}", "description": "Dept"},
        headers=headers,
    )
    assert department.status_code == 201, department.text
    department_id = department.json()["id"]

    course = client.post(
        "/api/courses",
        json={
            "department_id": department_id,
            "name": f"Course {suffix}",
            "code": f"C{suffix}",
            "degree": "Bachelor of Engineering",
            "duration_years": 4,
            "description": "Test course",
        },
        headers=headers,
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]

    academic_year = client.post(
        "/api/academic-years",
        json={"name": f"202{suffix[:2]}-{suffix[2:4]}", "start_date": "2026-06-01", "end_date": "2027-05-31", "is_current": True},
        headers=headers,
    )
    assert academic_year.status_code == 201, academic_year.text
    academic_year_id = academic_year.json()["id"]

    semester = client.post(
        "/api/semesters",
        json={
            "course_id": course_id,
            "academic_year_id": academic_year_id,
            "semester_number": 5,
            "name": "Semester 5",
            "start_date": "2026-06-01",
            "end_date": "2026-11-30",
            "is_active": True,
        },
        headers=headers,
    )
    assert semester.status_code == 201, semester.text
    semester_id = semester.json()["id"]

    section = client.post(
        "/api/sections",
        json={
            "semester_id": semester_id,
            "name": "Section A",
            "code": "A",
            "capacity": 60,
            "room_number": "CSE-301",
            "is_active": True,
        },
        headers=headers,
    )
    assert section.status_code == 201, section.text
    assert section.json()["name"] == "Section A"

    duplicate = client.post(
        "/api/sections",
        json={
            "semester_id": semester_id,
            "name": "Section A Duplicate",
            "code": "A",
            "capacity": 50,
            "room_number": "CSE-302",
            "is_active": True,
        },
        headers=headers,
    )
    assert duplicate.status_code == 400, duplicate.text

    second_semester = client.post(
        "/api/semesters",
        json={
            "course_id": course_id,
            "academic_year_id": academic_year_id,
            "semester_number": 6,
            "name": "Semester 6",
            "start_date": "2026-12-01",
            "end_date": "2027-05-31",
            "is_active": True,
        },
        headers=headers,
    )
    assert second_semester.status_code == 201, second_semester.text
    second_semester_id = second_semester.json()["id"]

    valid_cross_semester = client.post(
        "/api/sections",
        json={
            "semester_id": second_semester_id,
            "name": "Section A",
            "code": "A",
            "capacity": 45,
            "room_number": "CSE-401",
            "is_active": True,
        },
        headers=headers,
    )
    assert valid_cross_semester.status_code == 201, valid_cross_semester.text


def test_section_capacity_and_missing_semester_validation():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}

    # A capacity of zero never reaches the service: the schema's gt=0 rejects
    # it first, which is a 422. Asserting 400/404 here only passed while the
    # bound was missing from the schema.
    invalid_capacity = client.post(
        "/api/sections",
        json={
            "semester_id": 999,
            "name": "Section Invalid",
            "code": "Z",
            "capacity": 0,
            "room_number": "CSE-999",
            "is_active": True,
        },
        headers=headers,
    )
    assert invalid_capacity.status_code == 422, invalid_capacity.text
    assert invalid_capacity.json()["detail"][0]["loc"][-1] == "capacity"

    missing_semester = client.post(
        "/api/sections",
        json={
            "semester_id": 9999,
            "name": "Section Missing",
            "code": "M",
            "capacity": 30,
            "room_number": "CSE-100",
            "is_active": True,
        },
        headers=headers,
    )
    assert missing_semester.status_code == 404, missing_semester.text
