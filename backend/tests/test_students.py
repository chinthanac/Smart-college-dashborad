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
    """Create a full Department → Course → Year → Semester → Section chain."""
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
        json={
            "name": f"AY-{suffix}",
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
            "is_current": False,
        },
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
    semester_id = semester.json()["id"]

    section = client.post(
        "/api/sections",
        json={
            "semester_id": semester_id,
            "name": "Section A",
            "code": "A",
            "capacity": 60,
            "room_number": f"R-{suffix}",
            "is_active": True,
        },
        headers=headers,
    )
    assert section.status_code == 201, section.text
    section_id = section.json()["id"]

    return {
        "department_id": department_id,
        "course_id": course_id,
        "academic_year_id": academic_year_id,
        "semester_id": semester_id,
        "section_id": section_id,
    }


def student_payload(suffix, chain, **overrides):
    payload = {
        "student_id": f"STU{suffix}",
        "first_name": "Rahul",
        "last_name": "Kumar",
        "date_of_birth": "2005-05-15",
        "gender": "Male",
        "phone": "9876543210",
        "address": "12 College Road",
        "email": f"rahul.{suffix}@college.edu",
        "admission_date": "2026-07-01",
        "status": "ACTIVE",
        **chain,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# Test 1 — create a valid student
# --------------------------------------------------------------------------

def test_create_student_creates_user_and_student_records():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    response = client.post("/api/students", json=student_payload(suffix, chain), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["student_id"] == f"STU{suffix}".upper()
    assert body["full_name"] == "Rahul Kumar"
    assert body["user_id"] > 0
    assert body["status"] == "ACTIVE"
    # every level of the hierarchy is resolved back onto the record
    assert body["department_name"] and body["course_name"]
    assert body["academic_year_name"] and body["semester_name"] and body["section_name"]
    assert body["generated_password"]

    login = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["role"] == "STUDENT"


def test_admin_supplied_temporary_password_is_used():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    response = client.post(
        "/api/students",
        json=student_payload(suffix, chain, password="Temp@12345"),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    # nothing is generated when the Admin sets the password themselves
    assert response.json()["generated_password"] is None

    login = client.post(
        "/api/auth/login",
        json={"email": response.json()["email"], "password": "Temp@12345"},
    )
    assert login.status_code == 200, login.text


# --------------------------------------------------------------------------
# Tests 2 & 3 — duplicates
# --------------------------------------------------------------------------

def test_duplicate_student_id_and_email_are_rejected():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    first = client.post("/api/students", json=student_payload(suffix, chain), headers=headers)
    assert first.status_code == 201, first.text

    duplicate_id = client.post(
        "/api/students",
        json=student_payload(suffix, chain, email=f"other.{suffix}@college.edu"),
        headers=headers,
    )
    assert duplicate_id.status_code == 409, duplicate_id.text
    assert "already exists" in duplicate_id.json()["detail"]

    duplicate_email = client.post(
        "/api/students",
        json=student_payload(suffix, chain, student_id=f"STUX{suffix}"),
        headers=headers,
    )
    assert duplicate_email.status_code == 409, duplicate_email.text
    assert "already exists" in duplicate_email.json()["detail"]


# --------------------------------------------------------------------------
# Tests 4, 5 & 6 — the academic hierarchy must hold together
# --------------------------------------------------------------------------

def test_course_must_belong_to_selected_department():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    response = client.post(
        "/api/students",
        json=student_payload(suffix, {**chain, "department_id": other_chain["department_id"]}),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Course does not belong to selected department."


def test_semester_must_belong_to_selected_course():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    response = client.post(
        "/api/students",
        json=student_payload(suffix, {**chain, "semester_id": other_chain["semester_id"]}),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Semester does not belong to selected course."


def test_semester_must_belong_to_selected_academic_year():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    # a second year on the SAME course, so only the year is mismatched
    second_year = client.post(
        "/api/academic-years",
        json={
            "name": f"AY2-{suffix}",
            "start_date": "2027-06-01",
            "end_date": "2028-05-31",
            "is_current": False,
        },
        headers=headers,
    )
    assert second_year.status_code == 201, second_year.text

    response = client.post(
        "/api/students",
        json=student_payload(suffix, {**chain, "academic_year_id": second_year.json()["id"]}),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Semester does not belong to selected academic year."


def test_section_must_belong_to_selected_semester():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    response = client.post(
        "/api/students",
        json=student_payload(suffix, {**chain, "section_id": other_chain["section_id"]}),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Section does not belong to selected semester."


def test_field_level_validation():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    invalid_email = client.post(
        "/api/students",
        json=student_payload(suffix, chain, email="not-an-email"),
        headers=headers,
    )
    assert invalid_email.status_code == 400, invalid_email.text

    invalid_phone = client.post(
        "/api/students",
        json=student_payload(suffix, chain, phone="123"),
        headers=headers,
    )
    assert invalid_phone.status_code in (400, 422), invalid_phone.text

    invalid_gender = client.post(
        "/api/students",
        json=student_payload(suffix, chain, gender="Wizard"),
        headers=headers,
    )
    assert invalid_gender.status_code == 400, invalid_gender.text

    invalid_status = client.post(
        "/api/students",
        json=student_payload(suffix, chain, status="RETIRED"),
        headers=headers,
    )
    assert invalid_status.status_code == 400, invalid_status.text


# --------------------------------------------------------------------------
# search and filters
# --------------------------------------------------------------------------

def test_search_and_hierarchy_filters():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    created = client.post(
        "/api/students",
        json=student_payload(suffix, chain, first_name="Priyanka"),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    student_pk = created.json()["id"]

    searched = client.get("/api/students", params={"search": "priyanka"}, headers=headers)
    assert searched.status_code == 200, searched.text
    assert any(item["id"] == student_pk for item in searched.json())

    for key in ("department_id", "course_id", "academic_year_id", "semester_id", "section_id"):
        included = client.get("/api/students", params={key: chain[key]}, headers=headers)
        assert included.status_code == 200, included.text
        assert any(item["id"] == student_pk for item in included.json()), key

        excluded = client.get("/api/students", params={key: other_chain[key]}, headers=headers)
        assert excluded.status_code == 200, excluded.text
        assert all(item["id"] != student_pk for item in excluded.json()), key

    by_status = client.get("/api/students", params={"status": "GRADUATED"}, headers=headers)
    assert by_status.status_code == 200, by_status.text
    assert all(item["id"] != student_pk for item in by_status.json())


# --------------------------------------------------------------------------
# Test 8 — status changes gate login
# --------------------------------------------------------------------------

def test_deactivated_student_cannot_log_in():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    created = client.post("/api/students", json=student_payload(suffix, chain), headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()

    deactivated = client.patch(f"/api/students/{body['id']}/deactivate", headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["status"] == "INACTIVE"

    blocked = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert blocked.status_code == 401, blocked.text

    reactivated = client.patch(f"/api/students/{body['id']}/activate", headers=headers)
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["status"] == "ACTIVE"

    allowed = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert allowed.status_code == 200, allowed.text

    # graduating also revokes access while keeping the record
    graduated = client.patch(
        f"/api/students/{body['id']}/status",
        json={"status": "GRADUATED"},
        headers=headers,
    )
    assert graduated.status_code == 200, graduated.text
    assert graduated.json()["status"] == "GRADUATED"

    after_graduation = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert after_graduation.status_code == 401, after_graduation.text


# --------------------------------------------------------------------------
# Test 7 — authorization matrix
# --------------------------------------------------------------------------

def test_student_cannot_reach_admin_endpoints():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    created = client.post("/api/students", json=student_payload(suffix, chain), headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()

    login = client.post(
        "/api/auth/login",
        json={"email": body["email"], "password": body["generated_password"]},
    )
    assert login.status_code == 200, login.text
    student_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/students", headers=student_headers).status_code == 403
    assert client.get("/api/departments", headers=student_headers).status_code == 403
    assert client.get("/api/faculty", headers=student_headers).status_code == 403
    assert client.post(
        "/api/students",
        json=student_payload(uuid.uuid4().hex[:6], chain),
        headers=student_headers,
    ).status_code == 403
    assert client.patch(f"/api/students/{body['id']}/deactivate", headers=student_headers).status_code == 403

    profile = client.get("/api/students/me/profile", headers=student_headers)
    assert profile.status_code == 200, profile.text
    assert profile.json()["student_id"] == body["student_id"]

    updated = client.put(
        "/api/students/me/profile",
        json={"phone": "9876500000", "address": "New Hostel Block C"},
        headers=student_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["phone"] == "9876500000"


def test_faculty_can_only_see_their_own_department():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    mine = client.post("/api/students", json=student_payload(suffix, chain), headers=headers)
    assert mine.status_code == 201, mine.text
    theirs = client.post("/api/students", json=student_payload(other_suffix, other_chain), headers=headers)
    assert theirs.status_code == 201, theirs.text

    faculty = client.post(
        "/api/faculty",
        json={
            "faculty_id": f"FACS{suffix}",
            "department_id": chain["department_id"],
            "first_name": "Dept",
            "last_name": "Lecturer",
            "email": f"lecturer.{suffix}@college.edu",
            "phone": "9876543211",
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

    listed = client.get("/api/students", headers=faculty_headers)
    assert listed.status_code == 200, listed.text
    ids = [item["id"] for item in listed.json()]
    assert mine.json()["id"] in ids
    assert theirs.json()["id"] not in ids
    # the scope holds even when another department is asked for explicitly
    forced = client.get(
        "/api/students",
        params={"department_id": other_chain["department_id"]},
        headers=faculty_headers,
    )
    assert forced.status_code == 200, forced.text
    assert all(item["id"] != theirs.json()["id"] for item in forced.json())

    assert client.get(f"/api/students/{mine.json()['id']}", headers=faculty_headers).status_code == 200
    assert client.get(f"/api/students/{theirs.json()['id']}", headers=faculty_headers).status_code == 403
    # read-only: Faculty may look, never write
    assert client.post(
        "/api/students",
        json=student_payload(uuid.uuid4().hex[:6], chain),
        headers=faculty_headers,
    ).status_code == 403


# --------------------------------------------------------------------------
# edit, id suggestion, dependent-dropdown API
# --------------------------------------------------------------------------

def test_update_student_revalidates_the_hierarchy():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    created = client.post("/api/students", json=student_payload(suffix, chain), headers=headers)
    assert created.status_code == 201, created.text
    student_pk = created.json()["id"]

    valid = client.put(
        f"/api/students/{student_pk}",
        json=student_payload(suffix, chain, first_name="Rahulraj"),
        headers=headers,
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["first_name"] == "Rahulraj"

    broken = client.put(
        f"/api/students/{student_pk}",
        json=student_payload(suffix, {**chain, "section_id": other_chain["section_id"]}),
        headers=headers,
    )
    assert broken.status_code == 400, broken.text
    assert broken.json()["detail"] == "Section does not belong to selected semester."


def test_student_id_suggestion_increments():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    params = {"department_id": chain["department_id"], "academic_year_id": chain["academic_year_id"]}
    first = client.get("/api/students/suggest-id", params=params, headers=headers)
    assert first.status_code == 200, first.text
    suggested = first.json()["suggested_student_id"]
    assert suggested.endswith("001")

    created = client.post(
        "/api/students",
        json=student_payload(suffix, chain, student_id=suggested),
        headers=headers,
    )
    assert created.status_code == 201, created.text

    second = client.get("/api/students/suggest-id", params=params, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["suggested_student_id"] != suggested
    assert second.json()["suggested_student_id"].endswith("002")


def test_dependent_dropdown_endpoints():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    courses = client.get("/api/courses", params={"department_id": chain["department_id"]}, headers=headers)
    assert courses.status_code == 200, courses.text
    assert [c["id"] for c in courses.json()] == [chain["course_id"]]

    years = client.get("/api/academic-years", params={"course_id": chain["course_id"]}, headers=headers)
    assert years.status_code == 200, years.text
    assert [y["id"] for y in years.json()] == [chain["academic_year_id"]]
    assert other_chain["academic_year_id"] not in [y["id"] for y in years.json()]

    semesters = client.get(
        "/api/semesters",
        params={"course_id": chain["course_id"], "academic_year_id": chain["academic_year_id"]},
        headers=headers,
    )
    assert semesters.status_code == 200, semesters.text
    assert [s["id"] for s in semesters.json()] == [chain["semester_id"]]

    sections = client.get("/api/sections", params={"semester_id": chain["semester_id"]}, headers=headers)
    assert sections.status_code == 200, sections.text
    assert [s["id"] for s in sections.json()] == [chain["section_id"]]


def test_student_options_are_served():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/students/options", headers=headers)
    assert response.status_code == 200, response.text
    assert "Male" in response.json()["genders"]
    assert response.json()["statuses"] == ["ACTIVE", "INACTIVE", "GRADUATED", "SUSPENDED"]
