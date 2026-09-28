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

    return {
        "department_id": department_id,
        "course_id": course_id,
        "academic_year_id": academic_year_id,
        "semester_id": semester_id,
        "section_id": section.json()["id"],
    }


def create_extra_section(headers, semester_id, code):
    response = client.post(
        "/api/sections",
        json={
            "semester_id": semester_id,
            "name": f"Section {code}",
            "code": code,
            "capacity": 60,
            "room_number": f"R-{code}-{uuid.uuid4().hex[:4]}",
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def make_subject(headers, suffix, chain, **overrides):
    payload = {
        "course_id": chain["course_id"],
        "semester_id": chain["semester_id"],
        "subject_code": f"SUB{suffix}",
        "name": "Database Management Systems",
        "credits": 4,
        "subject_type": "THEORY",
        "lecture_hours": 3,
        "tutorial_hours": 1,
        "practical_hours": 0,
        "is_active": True,
    }
    payload.update(overrides)
    response = client.post("/api/subjects", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def make_faculty(headers, suffix, department_id, **overrides):
    payload = {
        "faculty_id": f"FACTA{suffix}",
        "department_id": department_id,
        "first_name": "Rahul",
        "last_name": "Sharma",
        "email": f"ta.{suffix}@college.edu",
        "phone": "9876543210",
        "designation": "Assistant Professor",
        "qualification": "Ph.D",
        "joining_date": "2026-07-01",
        "employee_type": "Full Time",
        "is_active": True,
    }
    payload.update(overrides)
    response = client.post("/api/faculty", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def assignment_payload(faculty_id, subject_id, section_id, **overrides):
    payload = {
        "faculty_id": faculty_id,
        "subject_id": subject_id,
        "section_id": section_id,
        "notes": None,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def setup_basics(headers, suffix):
    """The common trio: a hierarchy, a subject in it, and a faculty member."""
    chain = build_hierarchy(headers, suffix)
    subject_id = make_subject(headers, suffix, chain)
    faculty = make_faculty(headers, suffix, chain["department_id"])
    return chain, subject_id, faculty


# --------------------------------------------------------------------------
# create and the core integrity rule
# --------------------------------------------------------------------------

def test_create_assignment_resolves_the_full_teaching_context():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    response = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["faculty_name"] == "Rahul Sharma"
    assert body["faculty_code"] == f"FACTA{suffix}".upper()
    assert body["faculty_designation"] == "Assistant Professor"
    assert body["subject_code"] == f"SUB{suffix}".upper()
    assert body["subject_name"] == "Database Management Systems"
    assert body["subject_credits"] == 4
    assert body["section_name"] == "Section A"
    assert body["section_code"] == "A"
    assert body["section_room_number"] == f"R-{suffix}"
    assert body["semester_id"] == chain["semester_id"]
    assert body["semester_number"] == 5
    assert body["course_id"] == chain["course_id"]
    assert body["department_id"] == chain["department_id"]
    assert body["academic_year_name"] == f"AY-{suffix}"
    assert body["is_cross_department"] is False
    assert body["is_active"] is True


def test_section_must_belong_to_the_subjects_semester():
    """The rule the whole module exists to enforce."""
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    response = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, other_chain["section_id"]),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Section does not belong to the subject's semester."


def test_two_sections_of_the_same_semester_get_independent_assignments():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty_a = setup_basics(headers, suffix)
    section_b = create_extra_section(headers, chain["semester_id"], "B")
    faculty_b = make_faculty(
        headers, uuid.uuid4().hex[:6], chain["department_id"], first_name="Priya", last_name="Nair"
    )

    first = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty_a["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty_b["id"], subject_id, section_b),
        headers=headers,
    )
    assert second.status_code == 201, second.text
    assert second.json()["faculty_name"] == "Priya Nair"

    listed = client.get("/api/teaching-assignments", params={"subject_id": subject_id}, headers=headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 2


# --------------------------------------------------------------------------
# uniqueness: one faculty per subject + section
# --------------------------------------------------------------------------

def test_one_faculty_per_subject_and_section():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    other_faculty = make_faculty(headers, uuid.uuid4().hex[:6], chain["department_id"])

    first = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert first.status_code == 201, first.text
    assignment_id = first.json()["id"]

    duplicate = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert duplicate.status_code == 409, duplicate.text
    assert "already assigned to this section" in duplicate.json()["detail"]

    # a different faculty for the same pair is the same conflict
    other = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(other_faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert other.status_code == 409, other.text

    # deactivating does not free the pair — the DB constraint is is_active-blind
    deactivated = client.patch(
        f"/api/teaching-assignments/{assignment_id}/status", json={"is_active": False}, headers=headers
    )
    assert deactivated.status_code == 200, deactivated.text

    still_conflicts = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(other_faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert still_conflicts.status_code == 409, still_conflicts.text


def test_reassigning_replaces_the_faculty():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    replacement = make_faculty(
        headers, uuid.uuid4().hex[:6], chain["department_id"], first_name="Meera", last_name="Iyer"
    )

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    updated = client.put(
        f"/api/teaching-assignments/{assignment_id}",
        json=assignment_payload(replacement["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["faculty_name"] == "Meera Iyer"

    # replaced, never duplicated
    listed = client.get(
        "/api/teaching-assignments",
        params={"subject_id": subject_id, "section_id": chain["section_id"]},
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def test_missing_faculty_subject_and_section_are_rejected():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    missing_faculty = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(999999, subject_id, chain["section_id"]),
        headers=headers,
    )
    assert missing_faculty.status_code == 404, missing_faculty.text
    assert missing_faculty.json()["detail"] == "Faculty not found"

    missing_subject = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], 999999, chain["section_id"]),
        headers=headers,
    )
    assert missing_subject.status_code == 404, missing_subject.text
    assert missing_subject.json()["detail"] == "Subject not found"

    missing_section = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, 999999),
        headers=headers,
    )
    assert missing_section.status_code == 404, missing_section.text
    assert missing_section.json()["detail"] == "Section not found"


def test_inactive_faculty_subject_or_section_cannot_be_assigned():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    assert client.patch(
        f"/api/faculty/{faculty['id']}/status", json={"is_active": False}, headers=headers
    ).status_code == 200
    inactive_faculty = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert inactive_faculty.status_code == 400, inactive_faculty.text
    assert inactive_faculty.json()["detail"] == "Faculty member is inactive and cannot be assigned to teach."
    assert client.patch(
        f"/api/faculty/{faculty['id']}/status", json={"is_active": True}, headers=headers
    ).status_code == 200

    assert client.patch(
        f"/api/subjects/{subject_id}/status", json={"is_active": False}, headers=headers
    ).status_code == 200
    inactive_subject = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert inactive_subject.status_code == 400, inactive_subject.text
    assert inactive_subject.json()["detail"] == "Subject is inactive and cannot be assigned."
    assert client.patch(
        f"/api/subjects/{subject_id}/status", json={"is_active": True}, headers=headers
    ).status_code == 200

    section = client.get(f"/api/sections/{chain['section_id']}", headers=headers).json()
    assert client.put(
        f"/api/sections/{chain['section_id']}",
        json={**{k: section[k] for k in ("semester_id", "name", "code", "capacity", "room_number")}, "is_active": False},
        headers=headers,
    ).status_code == 200
    inactive_section = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert inactive_section.status_code == 400, inactive_section.text
    assert inactive_section.json()["detail"] == "Section is inactive and cannot be assigned."


def test_cross_department_assignment_is_allowed():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain, subject_id, _ = setup_basics(headers, suffix)
    other_chain = build_hierarchy(headers, other_suffix)

    # a Maths lecturer teaching into a CSE semester is legitimate
    visiting = make_faculty(headers, other_suffix, other_chain["department_id"])

    response = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(visiting["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_cross_department"] is True
    assert body["faculty_department_id"] == other_chain["department_id"]
    assert body["department_id"] == chain["department_id"]
    assert body["faculty_department_name"]


# --------------------------------------------------------------------------
# read, filter, search
# --------------------------------------------------------------------------

def test_filters_and_search():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    other_chain, other_subject_id, other_faculty = setup_basics(headers, other_suffix)

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    other = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(other_faculty["id"], other_subject_id, other_chain["section_id"]),
        headers=headers,
    )
    assert other.status_code == 201, other.text

    matching = {
        "faculty_id": faculty["id"],
        "subject_id": subject_id,
        "section_id": chain["section_id"],
        "semester_id": chain["semester_id"],
        "course_id": chain["course_id"],
        "department_id": chain["department_id"],
        "academic_year_id": chain["academic_year_id"],
        "faculty_department_id": chain["department_id"],
    }
    non_matching = {
        "faculty_id": other_faculty["id"],
        "subject_id": other_subject_id,
        "section_id": other_chain["section_id"],
        "semester_id": other_chain["semester_id"],
        "course_id": other_chain["course_id"],
        "department_id": other_chain["department_id"],
        "academic_year_id": other_chain["academic_year_id"],
        "faculty_department_id": other_chain["department_id"],
    }

    for key, value in matching.items():
        included = client.get("/api/teaching-assignments", params={key: value}, headers=headers)
        assert included.status_code == 200, included.text
        assert any(item["id"] == assignment_id for item in included.json()), key

    for key, value in non_matching.items():
        excluded = client.get("/api/teaching-assignments", params={key: value}, headers=headers)
        assert excluded.status_code == 200, excluded.text
        assert all(item["id"] != assignment_id for item in excluded.json()), key

    for term in (f"SUB{suffix}", "Sharma", f"FACTA{suffix}", "Section A"):
        found = client.get("/api/teaching-assignments", params={"search": term}, headers=headers)
        assert found.status_code == 200, found.text
        assert any(item["id"] == assignment_id for item in found.json()), term

    active = client.get("/api/teaching-assignments", params={"is_active": True}, headers=headers)
    assert any(item["id"] == assignment_id for item in active.json())
    inactive = client.get("/api/teaching-assignments", params={"is_active": False}, headers=headers)
    assert all(item["id"] != assignment_id for item in inactive.json())

    single = client.get(f"/api/teaching-assignments/{assignment_id}", headers=headers)
    assert single.status_code == 200, single.text
    assert single.json()["id"] == assignment_id


def test_assignment_list_is_available_on_both_root_paths():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text

    without_slash = client.get("/api/teaching-assignments", headers=headers)
    with_slash = client.get("/api/teaching-assignments/", headers=headers)
    assert without_slash.status_code == 200, without_slash.text
    assert with_slash.status_code == 200, with_slash.text
    assert {i["id"] for i in without_slash.json()} == {i["id"] for i in with_slash.json()}


# --------------------------------------------------------------------------
# bulk assignment
# --------------------------------------------------------------------------

def test_bulk_assign_creates_one_row_per_section():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    section_b = create_extra_section(headers, chain["semester_id"], "B")
    section_c = create_extra_section(headers, chain["semester_id"], "C")

    response = client.post(
        "/api/teaching-assignments/bulk",
        json={
            "faculty_id": faculty["id"],
            "subject_id": subject_id,
            "section_ids": [chain["section_id"], section_b, section_c],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["created"]) == 3
    assert body["skipped"] == []
    assert all(row["subject_code"] and row["section_name"] for row in body["created"])


def test_bulk_assign_skips_sections_that_are_already_assigned():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    section_b = create_extra_section(headers, chain["semester_id"], "B")
    section_c = create_extra_section(headers, chain["semester_id"], "C")

    pre_existing = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert pre_existing.status_code == 201, pre_existing.text

    response = client.post(
        "/api/teaching-assignments/bulk",
        json={
            "faculty_id": faculty["id"],
            "subject_id": subject_id,
            "section_ids": [chain["section_id"], section_b, section_c],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["created"]) == 2
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["section_id"] == chain["section_id"]
    assert "Rahul Sharma" in body["skipped"][0]["reason"]

    total = client.get("/api/teaching-assignments", params={"subject_id": subject_id}, headers=headers)
    assert len(total.json()) == 3


def test_bulk_assign_rejects_a_section_from_another_semester():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    section_b = create_extra_section(headers, chain["semester_id"], "B")
    other_chain = build_hierarchy(headers, other_suffix)

    response = client.post(
        "/api/teaching-assignments/bulk",
        json={
            "faculty_id": faculty["id"],
            "subject_id": subject_id,
            "section_ids": [chain["section_id"], section_b, other_chain["section_id"]],
        },
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Section does not belong to the subject's semester."

    # all-or-nothing: the two valid sections must not have been written
    listed = client.get("/api/teaching-assignments", params={"subject_id": subject_id}, headers=headers)
    assert listed.json() == []


def test_bulk_assign_deduplicates_repeated_section_ids():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    response = client.post(
        "/api/teaching-assignments/bulk",
        json={
            "faculty_id": faculty["id"],
            "subject_id": subject_id,
            "section_ids": [chain["section_id"], chain["section_id"]],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["created"]) == 1
    assert response.json()["skipped"] == []


# --------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------

def test_deactivate_and_delete_assignment():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    deactivated = client.patch(
        f"/api/teaching-assignments/{assignment_id}/status", json={"is_active": False}, headers=headers
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False

    inactive_only = client.get("/api/teaching-assignments", params={"is_active": False}, headers=headers)
    assert any(item["id"] == assignment_id for item in inactive_only.json())
    active_only = client.get("/api/teaching-assignments", params={"is_active": True}, headers=headers)
    assert all(item["id"] != assignment_id for item in active_only.json())

    reactivated = client.patch(
        f"/api/teaching-assignments/{assignment_id}/status", json={"is_active": True}, headers=headers
    )
    assert reactivated.status_code == 200, reactivated.text

    deleted = client.delete(f"/api/teaching-assignments/{assignment_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/teaching-assignments/{assignment_id}", headers=headers).status_code == 404


# --------------------------------------------------------------------------
# integrity guards in the upstream modules
# --------------------------------------------------------------------------

def test_subject_semester_cannot_move_while_assignments_exist():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    second_semester = client.post(
        "/api/semesters",
        json={
            "course_id": chain["course_id"],
            "academic_year_id": chain["academic_year_id"],
            "semester_number": 6,
            "name": f"Semester 6 {suffix}",
            "start_date": "2026-12-01",
            "end_date": "2027-05-31",
            "is_active": True,
        },
        headers=headers,
    )
    assert second_semester.status_code == 201, second_semester.text

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text

    subject = client.get(f"/api/subjects/{subject_id}", headers=headers).json()
    move_payload = {
        **{
            k: subject[k]
            for k in (
                "course_id", "subject_code", "name", "description", "credits",
                "subject_type", "lecture_hours", "tutorial_hours", "practical_hours", "is_active",
            )
        },
        "semester_id": second_semester.json()["id"],
    }

    blocked = client.put(f"/api/subjects/{subject_id}", json=move_payload, headers=headers)
    assert blocked.status_code == 400, blocked.text
    assert "Remove those teaching assignments before moving it." in blocked.json()["detail"]

    assert client.delete(f"/api/teaching-assignments/{created.json()['id']}", headers=headers).status_code == 204
    allowed = client.put(f"/api/subjects/{subject_id}", json=move_payload, headers=headers)
    assert allowed.status_code == 200, allowed.text


def test_section_semester_cannot_move_while_assignments_exist():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    second_semester = client.post(
        "/api/semesters",
        json={
            "course_id": chain["course_id"],
            "academic_year_id": chain["academic_year_id"],
            "semester_number": 6,
            "name": f"Semester 6 {suffix}",
            "start_date": "2026-12-01",
            "end_date": "2027-05-31",
            "is_active": True,
        },
        headers=headers,
    )
    assert second_semester.status_code == 201, second_semester.text

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text

    section = client.get(f"/api/sections/{chain['section_id']}", headers=headers).json()
    move_payload = {
        **{k: section[k] for k in ("name", "code", "capacity", "room_number", "is_active")},
        "semester_id": second_semester.json()["id"],
    }

    blocked = client.put(f"/api/sections/{chain['section_id']}", json=move_payload, headers=headers)
    assert blocked.status_code == 400, blocked.text
    assert "Remove them before moving it." in blocked.json()["detail"]

    assert client.delete(f"/api/teaching-assignments/{created.json()['id']}", headers=headers).status_code == 204
    allowed = client.put(f"/api/sections/{chain['section_id']}", json=move_payload, headers=headers)
    assert allowed.status_code == 200, allowed.text


def test_deleting_linked_records_is_blocked_while_assignments_exist():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    blocked_subject = client.delete(f"/api/subjects/{subject_id}", headers=headers)
    assert blocked_subject.status_code == 409, blocked_subject.text
    assert "teaching assignment(s)" in blocked_subject.json()["detail"]

    blocked_section = client.delete(f"/api/sections/{chain['section_id']}", headers=headers)
    assert blocked_section.status_code == 409, blocked_section.text

    blocked_faculty = client.delete(f"/api/faculty/{faculty['id']}", headers=headers)
    assert blocked_faculty.status_code == 409, blocked_faculty.text

    assert client.delete(f"/api/teaching-assignments/{assignment_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/subjects/{subject_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/sections/{chain['section_id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/faculty/{faculty['id']}", headers=headers).status_code == 204


# --------------------------------------------------------------------------
# authorization
# --------------------------------------------------------------------------

def test_faculty_can_read_their_own_assignments_via_me():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    bystander = make_faculty(headers, uuid.uuid4().hex[:6], chain["department_id"])

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text

    login = client.post(
        "/api/auth/login",
        json={"email": faculty["email"], "password": faculty["generated_password"]},
    )
    assert login.status_code == 200, login.text
    faculty_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    mine = client.get("/api/teaching-assignments/me", headers=faculty_headers)
    assert mine.status_code == 200, mine.text
    assert [item["id"] for item in mine.json()] == [created.json()["id"]]
    assert mine.json()[0]["subject_code"] and mine.json()[0]["section_name"]

    other_login = client.post(
        "/api/auth/login",
        json={"email": bystander["email"], "password": bystander["generated_password"]},
    )
    assert other_login.status_code == 200, other_login.text
    empty = client.get(
        "/api/teaching-assignments/me",
        headers={"Authorization": f"Bearer {other_login.json()['access_token']}"},
    )
    assert empty.status_code == 200, empty.text
    assert empty.json() == []

    # /me is for faculty only
    assert client.get("/api/teaching-assignments/me", headers=headers).status_code == 403


def test_faculty_reads_are_scoped_to_their_department():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    other_suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    other_chain, other_subject_id, other_faculty = setup_basics(headers, other_suffix)

    mine = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert mine.status_code == 201, mine.text
    theirs = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(other_faculty["id"], other_subject_id, other_chain["section_id"]),
        headers=headers,
    )
    assert theirs.status_code == 201, theirs.text

    login = client.post(
        "/api/auth/login",
        json={"email": faculty["email"], "password": faculty["generated_password"]},
    )
    assert login.status_code == 200, login.text
    faculty_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    listed = client.get("/api/teaching-assignments", headers=faculty_headers)
    assert listed.status_code == 200, listed.text
    ids = [item["id"] for item in listed.json()]
    assert mine.json()["id"] in ids
    assert theirs.json()["id"] not in ids

    forced = client.get(
        "/api/teaching-assignments",
        params={"department_id": other_chain["department_id"]},
        headers=faculty_headers,
    )
    assert forced.status_code == 200, forced.text
    assert all(item["id"] != theirs.json()["id"] for item in forced.json())

    assert client.get(f"/api/teaching-assignments/{mine.json()['id']}", headers=faculty_headers).status_code == 200
    blocked = client.get(f"/api/teaching-assignments/{theirs.json()['id']}", headers=faculty_headers)
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["detail"] == "You can only view teaching assignments from your own department."


def test_only_admin_can_write_teaching_assignments():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)
    section_b = create_extra_section(headers, chain["semester_id"], "B")

    created = client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    login = client.post(
        "/api/auth/login",
        json={"email": faculty["email"], "password": faculty["generated_password"]},
    )
    assert login.status_code == 200, login.text
    faculty_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, section_b),
        headers=faculty_headers,
    ).status_code == 403
    assert client.post(
        "/api/teaching-assignments/bulk",
        json={"faculty_id": faculty["id"], "subject_id": subject_id, "section_ids": [section_b]},
        headers=faculty_headers,
    ).status_code == 403
    assert client.put(
        f"/api/teaching-assignments/{assignment_id}",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=faculty_headers,
    ).status_code == 403
    assert client.patch(
        f"/api/teaching-assignments/{assignment_id}/status",
        json={"is_active": False},
        headers=faculty_headers,
    ).status_code == 403
    assert client.delete(
        f"/api/teaching-assignments/{assignment_id}", headers=faculty_headers
    ).status_code == 403


def test_students_cannot_reach_teaching_assignment_endpoints():
    token = login_admin()
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty = setup_basics(headers, suffix)

    student = client.post(
        "/api/students",
        json={
            "student_id": f"STUTA{suffix}",
            "first_name": "Test",
            "last_name": "Student",
            "email": f"tastudent.{suffix}@college.edu",
            "phone": "9876543214",
            "department_id": chain["department_id"],
            "course_id": chain["course_id"],
            "academic_year_id": chain["academic_year_id"],
            "semester_id": chain["semester_id"],
            "section_id": chain["section_id"],
            "status": "ACTIVE",
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

    assert client.get("/api/teaching-assignments", headers=student_headers).status_code == 403
    assert client.get("/api/teaching-assignments/me", headers=student_headers).status_code == 403
    assert client.post(
        "/api/teaching-assignments",
        json=assignment_payload(faculty["id"], subject_id, chain["section_id"]),
        headers=student_headers,
    ).status_code == 403
