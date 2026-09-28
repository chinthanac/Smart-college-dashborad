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


def test_create_semester_success_and_duplicate_rejected():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}

    # Unique per run. The department code, course code and academic year name
    # are all unique columns, and the hardcoded "CSE" / "BE-CSE" / "2026-27"
    # these used to be collided with test_academic_years' own fixtures — so
    # this test passed alone and failed in a full run, which is the worst of
    # both worlds.
    suffix = uuid.uuid4().hex[:6]

    course = client.post(
        "/api/departments",
        json={
            "name": f"Computer Science and Engineering {suffix}",
            "code": f"CSE{suffix}",
            "description": "Dept",
        },
        headers=headers,
    )
    assert course.status_code == 201, course.text

    dept_id = course.json()["id"]
    course_response = client.post(
        "/api/courses",
        json={
            "department_id": dept_id,
            "name": f"B.E. Computer Science & Engineering {suffix}",
            "code": f"BE-CSE{suffix}",
            "degree": "Bachelor of Engineering",
            "duration_years": 4,
            "description": "Test course",
        },
        headers=headers,
    )
    assert course_response.status_code == 201, course_response.text
    course_id = course_response.json()["id"]

    academic_year = client.post(
        "/api/academic-years",
        json={
            "name": f"2026-27-{suffix}",
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
            "is_current": True,
        },
        headers=headers,
    )
    assert academic_year.status_code == 201, academic_year.text
    academic_year_id = academic_year.json()["id"]

    sem = client.post(
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
    assert sem.status_code == 201, sem.text
    assert sem.json()["name"] == "Semester 5"

    duplicate = client.post(
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
    assert duplicate.status_code == 400, duplicate.text


def test_invalid_semester_dates_and_missing_course():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}

    invalid = client.post(
        "/api/semesters",
        json={
            "course_id": 999,
            "academic_year_id": 999,
            "semester_number": 4,
            "name": "Semester 4",
            "start_date": "2026-12-01",
            "end_date": "2026-06-30",
            "is_active": True,
        },
        headers=headers,
    )
    assert invalid.status_code == 404 or invalid.status_code == 400, invalid.text
