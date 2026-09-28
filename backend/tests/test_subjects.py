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


def build_hierarchy(headers, suffix):
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
        json={"name": f"AY-{suffix}", "start_date": "2026-06-01", "end_date": "2027-05-31", "is_current": False},
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
            "name": f"Semester 5 {suffix}",
            "start_date": "2026-06-01",
            "end_date": "2026-11-30",
            "is_active": True,
        },
        headers=headers,
    )
    assert semester.status_code == 201, semester.text

    return {
        "department_id": department_id,
        "course_id": course_id,
        "academic_year_id": academic_year_id,
        "semester_id": semester.json()["id"],
    }


def subject_payload(suffix, chain, **overrides):
    payload = {
        "course_id": chain["course_id"],
        "semester_id": chain["semester_id"],
        "subject_code": f"CS{suffix}",
        "name": "Database Management Systems",
        "description": "Relational modelling, SQL, transactions.",
        "credits": 4,
        "subject_type": "THEORY",
        "lecture_hours": 3,
        "tutorial_hours": 1,
        "practical_hours": 0,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# create
# --------------------------------------------------------------------------

def test_create_subject_resolves_the_academic_structure():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    response = client.post("/api/subjects", json=subject_payload(suffix, chain), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["subject_code"] == f"CS{suffix}".upper()
    assert body["name"] == "Database Management Systems"
    assert body["credits"] == 4
    assert body["subject_type"] == "THEORY"
    assert body["total_hours"] == 4
    # the course, semester, and department are resolved onto the record
    assert body["course_name"] and body["semester_name"]
    assert body["department_id"] == chain["department_id"]
    assert body["academic_year_name"]


def test_subject_code_is_normalized_and_globally_unique():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    first = client.post(
        "/api/subjects",
        json=subject_payload(suffix, chain, subject_code=f"cs{suffix}"),
        headers=headers,
    )
    assert first.status_code == 201, first.text
    assert first.json()["subject_code"] == f"CS{suffix}".upper()

    same_place = client.post("/api/subjects", json=subject_payload(suffix, chain), headers=headers)
    assert same_place.status_code == 409, same_place.text

    # global uniqueness: the same code is rejected under a different course too
    elsewhere = client.post(
        "/api/subjects",
        json=subject_payload(suffix, other_chain, subject_code=f"CS{suffix}"),
        headers=headers,
    )
    assert elsewhere.status_code == 409, elsewhere.text
    assert "already exists" in elsewhere.json()["detail"]


def test_semester_must_belong_to_selected_course():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    response = client.post(
        "/api/subjects",
        json=subject_payload(suffix, chain, semester_id=other_chain["semester_id"]),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Semester does not belong to selected course."


def test_missing_course_and_semester_are_rejected():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    missing_course = client.post(
        "/api/subjects",
        json=subject_payload(suffix, chain, course_id=999999),
        headers=headers,
    )
    assert missing_course.status_code == 404, missing_course.text

    missing_semester = client.post(
        "/api/subjects",
        json=subject_payload(suffix, chain, semester_id=999999),
        headers=headers,
    )
    assert missing_semester.status_code == 404, missing_semester.text


def test_credits_hours_type_and_name_validation():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    zero_credits = client.post(
        "/api/subjects", json=subject_payload(suffix, chain, credits=0), headers=headers
    )
    assert zero_credits.status_code in (400, 422), zero_credits.text

    negative_credits = client.post(
        "/api/subjects", json=subject_payload(suffix, chain, credits=-2), headers=headers
    )
    assert negative_credits.status_code in (400, 422), negative_credits.text

    negative_hours = client.post(
        "/api/subjects", json=subject_payload(suffix, chain, lecture_hours=-1), headers=headers
    )
    assert negative_hours.status_code in (400, 422), negative_hours.text

    no_hours_at_all = client.post(
        "/api/subjects",
        json=subject_payload(suffix, chain, lecture_hours=0, tutorial_hours=0, practical_hours=0),
        headers=headers,
    )
    assert no_hours_at_all.status_code == 400, no_hours_at_all.text

    bad_type = client.post(
        "/api/subjects", json=subject_payload(suffix, chain, subject_type="WORKSHOP"), headers=headers
    )
    assert bad_type.status_code == 400, bad_type.text

    blank_name = client.post(
        "/api/subjects", json=subject_payload(suffix, chain, name="   "), headers=headers
    )
    assert blank_name.status_code in (400, 422), blank_name.text


def test_lab_subject_with_only_practical_hours_is_allowed():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    response = client.post(
        "/api/subjects",
        json=subject_payload(
            suffix, chain,
            name="DBMS Laboratory", subject_type="LAB", credits=2,
            lecture_hours=0, tutorial_hours=0, practical_hours=4,
        ),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["subject_type"] == "LAB"
    assert response.json()["total_hours"] == 4


# --------------------------------------------------------------------------
# read, filter, search
# --------------------------------------------------------------------------

def test_filters_and_search():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    created = client.post("/api/subjects", json=subject_payload(suffix, chain), headers=headers)
    assert created.status_code == 201, created.text
    subject_pk = created.json()["id"]

    searched = client.get("/api/subjects", params={"search": "database"}, headers=headers)
    assert searched.status_code == 200, searched.text
    assert any(item["id"] == subject_pk for item in searched.json())

    for key in ("course_id", "semester_id", "department_id"):
        included = client.get("/api/subjects", params={key: chain[key]}, headers=headers)
        assert included.status_code == 200, included.text
        assert any(item["id"] == subject_pk for item in included.json()), key

        excluded = client.get("/api/subjects", params={key: other_chain[key]}, headers=headers)
        assert excluded.status_code == 200, excluded.text
        assert all(item["id"] != subject_pk for item in excluded.json()), key

    combined = client.get(
        "/api/subjects",
        params={"course_id": chain["course_id"], "semester_id": chain["semester_id"]},
        headers=headers,
    )
    assert combined.status_code == 200, combined.text
    assert [item["id"] for item in combined.json()] == [subject_pk]

    by_type = client.get("/api/subjects", params={"subject_type": "LAB"}, headers=headers)
    assert by_type.status_code == 200, by_type.text
    assert all(item["id"] != subject_pk for item in by_type.json())

    single = client.get(f"/api/subjects/{subject_pk}", headers=headers)
    assert single.status_code == 200, single.text
    assert single.json()["subject_code"] == created.json()["subject_code"]


# --------------------------------------------------------------------------
# update and deactivate
# --------------------------------------------------------------------------

def test_update_revalidates_and_deactivation_works():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    created = client.post("/api/subjects", json=subject_payload(suffix, chain), headers=headers)
    assert created.status_code == 201, created.text
    subject_pk = created.json()["id"]

    updated = client.put(
        f"/api/subjects/{subject_pk}",
        json=subject_payload(suffix, chain, name="Advanced DBMS", credits=5),
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Advanced DBMS"
    assert updated.json()["credits"] == 5

    broken = client.put(
        f"/api/subjects/{subject_pk}",
        json=subject_payload(suffix, chain, semester_id=other_chain["semester_id"]),
        headers=headers,
    )
    assert broken.status_code == 400, broken.text
    assert broken.json()["detail"] == "Semester does not belong to selected course."

    deactivated = client.patch(
        f"/api/subjects/{subject_pk}/status", json={"is_active": False}, headers=headers
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False

    inactive_only = client.get("/api/subjects", params={"is_active": False}, headers=headers)
    assert any(item["id"] == subject_pk for item in inactive_only.json())
    active_only = client.get("/api/subjects", params={"is_active": True}, headers=headers)
    assert all(item["id"] != subject_pk for item in active_only.json())

    reactivated = client.patch(
        f"/api/subjects/{subject_pk}/status", json={"is_active": True}, headers=headers
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["is_active"] is True

    deleted = client.delete(f"/api/subjects/{subject_pk}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/subjects/{subject_pk}", headers=headers).status_code == 404


# --------------------------------------------------------------------------
# authorization
# --------------------------------------------------------------------------

def test_only_admin_can_write_subjects():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    mine = client.post("/api/subjects", json=subject_payload(suffix, chain), headers=headers)
    assert mine.status_code == 201, mine.text
    theirs = client.post("/api/subjects", json=subject_payload(other_suffix, other_chain), headers=headers)
    assert theirs.status_code == 201, theirs.text

    faculty = client.post(
        "/api/faculty",
        json={
            "faculty_id": f"FACSUB{suffix}",
            "department_id": chain["department_id"],
            "first_name": "Subject",
            "last_name": "Lecturer",
            "email": f"sublecturer.{suffix}@college.edu",
            "phone": "9876543212",
            "designation": "Lecturer",
            "qualification": "M.Tech",
            "joining_date": "2026-07-01",
            "employee_type": "Full Time",
            "is_active": True,
        },
        headers=headers,
    )
    assert faculty.status_code == 201, faculty.text
    login = client.post(
        "/api/auth/login",
        json={"email": faculty.json()["email"], "password": faculty.json()["generated_password"]},
    )
    assert login.status_code == 200, login.text
    faculty_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Faculty may read, scoped to their own department
    listed = client.get("/api/subjects", headers=faculty_headers)
    assert listed.status_code == 200, listed.text
    ids = [item["id"] for item in listed.json()]
    assert mine.json()["id"] in ids
    assert theirs.json()["id"] not in ids
    assert client.get(f"/api/subjects/{theirs.json()['id']}", headers=faculty_headers).status_code == 403

    # ...but never write
    assert client.post(
        "/api/subjects", json=subject_payload(uuid.uuid4().hex[:6], chain), headers=faculty_headers
    ).status_code == 403
    assert client.put(
        f"/api/subjects/{mine.json()['id']}",
        json=subject_payload(suffix, chain),
        headers=faculty_headers,
    ).status_code == 403
    assert client.patch(
        f"/api/subjects/{mine.json()['id']}/status", json={"is_active": False}, headers=faculty_headers
    ).status_code == 403
    assert client.delete(f"/api/subjects/{mine.json()['id']}", headers=faculty_headers).status_code == 403


def test_students_cannot_reach_subject_endpoints_yet():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    section = client.post(
        "/api/sections",
        json={
            "semester_id": chain["semester_id"], "name": "Section A", "code": "A",
            "capacity": 60, "room_number": f"R-{suffix}", "is_active": True,
        },
        headers=headers,
    )
    assert section.status_code == 201, section.text

    student = client.post(
        "/api/students",
        json={
            "student_id": f"STUSUB{suffix}", "first_name": "Test", "last_name": "Student",
            "email": f"substudent.{suffix}@college.edu", "phone": "9876543213",
            "department_id": chain["department_id"], "course_id": chain["course_id"],
            "academic_year_id": chain["academic_year_id"], "semester_id": chain["semester_id"],
            "section_id": section.json()["id"], "status": "ACTIVE",
        },
        headers=headers,
    )
    assert student.status_code == 201, student.text

    login = client.post(
        "/api/auth/login",
        json={"email": student.json()["email"], "password": student.json()["generated_password"]},
    )
    assert login.status_code == 200, login.text
    student_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # students see subjects only through enrollment, which does not exist yet
    assert client.get("/api/subjects", headers=student_headers).status_code == 403
    assert client.post(
        "/api/subjects", json=subject_payload(suffix, chain), headers=student_headers
    ).status_code == 403


def test_subject_options_are_served():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/subjects/options", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["subject_types"] == ["THEORY", "LAB", "PROJECT", "SEMINAR", "ELECTIVE"]
