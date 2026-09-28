"""Assessments module.

Most of these tests are about the three ways an exam component can corrupt a
result: by claiming more of the subject than exists, by moving the ceiling
under a mark already awarded, and by reaching a student before anybody decided
it should. The weightage ledger, the max_marks guard and the DRAFT gate get
the most attention for that reason.

The cascade test at the bottom is the important structural one: deleting a
section must never take exam history with it.
"""

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


def admin_headers():
    return {"Authorization": f"Bearer {login_admin()}"}


def headers_for(email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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
        json={
            "name": f"AY-{suffix}",
            "start_date": "2026-01-01",
            "end_date": "2027-12-31",
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
            "code": f"A{suffix}",
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
        "faculty_id": f"FACAS{suffix}",
        "department_id": department_id,
        "first_name": "Meera",
        "last_name": "Iyer",
        "email": f"as.{suffix}@college.edu",
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


def make_student(headers, suffix, chain, **overrides):
    payload = {
        "student_id": f"STU{suffix}",
        "first_name": "Arjun",
        "last_name": "Menon",
        "phone": "9876500000",
        "email": f"stu.{suffix}@student.college.edu",
        "department_id": chain["department_id"],
        "course_id": chain["course_id"],
        "academic_year_id": chain["academic_year_id"],
        "semester_id": chain["semester_id"],
        "section_id": chain["section_id"],
        "status": "ACTIVE",
    }
    payload.update(overrides)
    response = client.post("/api/students", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def make_assignment(headers, faculty_id, subject_id, section_id):
    response = client.post(
        "/api/teaching-assignments",
        json={
            "faculty_id": faculty_id,
            "subject_id": subject_id,
            "section_id": section_id,
            "notes": None,
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def assessment_payload(assignment_id, **overrides):
    payload = {
        "teaching_assignment_id": assignment_id,
        "assessment_type": "INTERNAL",
        "name": "Internal 1",
        "sequence_no": 1,
        "max_marks": 50,
        "weightage_percent": 30,
    }
    payload.update(overrides)
    return payload


def make_assessment(headers, assignment_id, **overrides):
    response = client.post(
        "/api/assessments", json=assessment_payload(assignment_id, **overrides), headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def setup_class(headers, suffix, students=0):
    """A hierarchy, a subject, a faculty member and the assignment joining them."""
    chain = build_hierarchy(headers, suffix)
    subject_id = make_subject(headers, suffix, chain)
    faculty = make_faculty(headers, suffix, chain["department_id"])
    assignment_id = make_assignment(headers, faculty["id"], subject_id, chain["section_id"])

    roster = [
        make_student(headers, f"{suffix}{index}", chain) for index in range(students)
    ]

    return {
        "chain": chain,
        "subject_id": subject_id,
        "faculty": faculty,
        "assignment_id": assignment_id,
        "roster": roster,
    }


def seed_marks(assessment_id, student_ids, section_id=None, marks=None):
    """Put marks on file through the real endpoint.

    These tests need records to exercise the publish gate and the delete
    guard; how they get there is ``test_marks``'s subject, not this module's.
    """
    entries = [
        {
            "student_id": student_id,
            "marks_obtained": marks[index] if marks is not None else 40.0,
        }
        for index, student_id in enumerate(student_ids)
    ]
    response = client.post(
        "/api/marks/sheet",
        json={"assessment_id": assessment_id, "entries": entries},
        headers=admin_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# create, and the identity copied from the assignment
# --------------------------------------------------------------------------

def test_create_assessment_copies_its_identity_from_the_assignment():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)

    body = make_assessment(headers, setup["assignment_id"], name="Internal 1")

    assert body["teaching_assignment_id"] == setup["assignment_id"]
    assert body["faculty_id"] == setup["faculty"]["id"]
    assert body["subject_id"] == setup["subject_id"]
    assert body["section_id"] == setup["chain"]["section_id"]
    assert body["semester_id"] == setup["chain"]["semester_id"]

    assert body["subject_code"] == f"SUB{suffix}".upper()
    assert body["subject_credits"] == 4
    assert body["faculty_name"] == "Meera Iyer"
    assert body["section_name"] == "Section A"
    assert body["department_id"] == setup["chain"]["department_id"]

    # Born DRAFT, and therefore counting toward nothing.
    assert body["status"] == "DRAFT"
    assert body["counts_toward_result"] is False
    assert body["published_at"] is None
    assert body["locked_at"] is None
    assert body["is_active"] is True


def test_pass_marks_default_to_forty_percent_of_the_maximum():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    body = make_assessment(headers, setup["assignment_id"], max_marks=50)
    assert body["pass_marks"] == 20.0

    explicit = make_assessment(
        headers,
        setup["assignment_id"],
        assessment_type="ASSIGNMENT",
        name="Assignment 1",
        max_marks=20,
        weightage_percent=10,
        pass_marks=8,
    )
    assert explicit["pass_marks"] == 8.0


def test_pass_marks_above_the_maximum_are_rejected():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    response = client.post(
        "/api/assessments",
        json=assessment_payload(setup["assignment_id"], max_marks=50, pass_marks=60),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "cannot exceed" in response.json()["detail"]


def test_unknown_assessment_type_is_rejected_by_name():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    response = client.post(
        "/api/assessments",
        json=assessment_payload(setup["assignment_id"], assessment_type="VIVA"),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "VIVA" in response.json()["detail"]
    assert "INTERNAL" in response.json()["detail"]


def test_max_marks_and_weightage_are_rejected_at_the_payload_edge():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    for field, value in (("max_marks", 0), ("weightage_percent", 0), ("sequence_no", 0)):
        response = client.post(
            "/api/assessments",
            json=assessment_payload(setup["assignment_id"], **{field: value}),
            headers=headers,
        )
        assert response.status_code == 422, f"{field}: {response.text}"


def test_duplicate_component_is_rejected_with_a_route_out():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])
    make_assessment(headers, setup["assignment_id"])

    response = client.post(
        "/api/assessments",
        json=assessment_payload(setup["assignment_id"], name="Internal 1 again", weightage_percent=10),
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "different number" in response.json()["detail"]

    # The same type at a different number is a different component.
    second = client.post(
        "/api/assessments",
        json=assessment_payload(
            setup["assignment_id"], name="Internal 2", sequence_no=2, weightage_percent=30
        ),
        headers=headers,
    )
    assert second.status_code == 201, second.text


def test_assessment_cannot_be_created_on_a_paused_assignment():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    paused = client.patch(
        f"/api/teaching-assignments/{setup['assignment_id']}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert paused.status_code == 200, paused.text

    response = client.post(
        "/api/assessments", json=assessment_payload(setup["assignment_id"]), headers=headers
    )
    assert response.status_code == 400, response.text
    assert "paused" in response.json()["detail"]


def test_unknown_assignment_is_a_404():
    headers = admin_headers()
    response = client.post(
        "/api/assessments", json=assessment_payload(99999), headers=headers
    )
    assert response.status_code == 404, response.text


# --------------------------------------------------------------------------
# the weightage ledger
# --------------------------------------------------------------------------

def test_weightage_may_reach_exactly_one_hundred():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    make_assessment(headers, setup["assignment_id"], weightage_percent=30)
    make_assessment(
        headers,
        setup["assignment_id"],
        sequence_no=2,
        name="Internal 2",
        weightage_percent=30,
    )
    final = client.post(
        "/api/assessments",
        json=assessment_payload(
            setup["assignment_id"],
            assessment_type="EXTERNAL",
            name="End Semester",
            max_marks=100,
            weightage_percent=40,
        ),
        headers=headers,
    )
    assert final.status_code == 201, final.text

    budget = client.get(
        "/api/assessments/budget",
        params={"teaching_assignment_id": setup["assignment_id"]},
        headers=headers,
    )
    assert budget.status_code == 200, budget.text
    body = budget.json()
    assert body["allocated"] == 100.0
    assert body["remaining"] == 0.0
    assert body["is_fully_allocated"] is True
    assert len(body["consumers"]) == 3


def test_weightage_overflow_names_what_is_consuming_the_budget():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    make_assessment(headers, setup["assignment_id"], name="Internal 1", weightage_percent=30)
    make_assessment(
        headers,
        setup["assignment_id"],
        assessment_type="ASSIGNMENT",
        name="Assignment 1",
        max_marks=20,
        weightage_percent=20,
    )

    response = client.post(
        "/api/assessments",
        json=assessment_payload(
            setup["assignment_id"],
            assessment_type="EXTERNAL",
            name="End Semester",
            max_marks=100,
            weightage_percent=60,
        ),
        headers=headers,
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]

    # A bare "invalid weightage" would make the user guess which component to
    # shrink. The message has to name them and state the arithmetic.
    assert "Internal 1 (30.0%)" in detail
    assert "Assignment 1 (20.0%)" in detail
    assert "50.0%" in detail
    assert "60.0%" in detail


def test_editing_weightage_excludes_the_assessment_from_its_own_budget():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    first = make_assessment(headers, setup["assignment_id"], weightage_percent=60)
    make_assessment(
        headers,
        setup["assignment_id"],
        sequence_no=2,
        name="Internal 2",
        weightage_percent=40,
    )

    # 70 does not fit beside the other 40 ...
    overflow = client.patch(
        f"/api/assessments/{first['id']}", json={"weightage_percent": 70}, headers=headers
    )
    assert overflow.status_code == 400, overflow.text

    # ... but 55 does, and the row's own 60 must not be counted against it.
    ok = client.patch(
        f"/api/assessments/{first['id']}", json={"weightage_percent": 55}, headers=headers
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["weightage_percent"] == 55.0


def test_deactivated_assessment_releases_its_share_of_the_budget():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    first = make_assessment(headers, setup["assignment_id"], weightage_percent=60)
    client.patch(f"/api/assessments/{first['id']}", json={"is_active": False}, headers=headers)

    response = client.post(
        "/api/assessments",
        json=assessment_payload(
            setup["assignment_id"], sequence_no=2, name="Internal 2", weightage_percent=80
        ),
        headers=headers,
    )
    assert response.status_code == 201, response.text


def test_budget_on_an_empty_class_is_the_whole_hundred():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])

    response = client.get(
        "/api/assessments/budget",
        params={"teaching_assignment_id": setup["assignment_id"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["allocated"] == 0.0
    assert body["remaining"] == 100.0
    assert body["is_fully_allocated"] is False
    assert body["consumers"] == []


# --------------------------------------------------------------------------
# max_marks can never fall under a mark already awarded
# --------------------------------------------------------------------------

def test_max_marks_cannot_be_lowered_under_an_awarded_mark():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    assessment = make_assessment(headers, setup["assignment_id"], max_marks=50)

    seed_marks(
        assessment["id"],
        [student["id"] for student in setup["roster"]],
        setup["chain"]["section_id"],
        marks=[45.0, 30.0],
    )

    response = client.patch(
        f"/api/assessments/{assessment['id']}", json={"max_marks": 40}, headers=headers
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "45.0" in detail
    assert "40.0" in detail

    # Raising it is always safe.
    raised = client.patch(
        f"/api/assessments/{assessment['id']}", json={"max_marks": 60}, headers=headers
    )
    assert raised.status_code == 200, raised.text
    # An unset pass mark tracks the new maximum rather than going stale.
    assert raised.json()["pass_marks"] == 24.0


# --------------------------------------------------------------------------
# status: DRAFT reaches nobody
# --------------------------------------------------------------------------

def test_publishing_requires_marks_on_file():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    assessment = make_assessment(headers, setup["assignment_id"])

    empty = client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "publish"}, headers=headers
    )
    assert empty.status_code == 400, empty.text
    assert "nothing to publish" in empty.json()["detail"]

    seed_marks(
        assessment["id"],
        [setup["roster"][0]["id"]],
        setup["chain"]["section_id"],
    )
    published = client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "publish"}, headers=headers
    )
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["status"] == "PUBLISHED"
    assert body["published_at"] is not None
    assert body["counts_toward_result"] is True


def test_status_transitions_run_draft_to_published_to_locked():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    assessment = make_assessment(headers, setup["assignment_id"])
    seed_marks(assessment["id"], [setup["roster"][0]["id"]], setup["chain"]["section_id"])

    # A draft cannot be locked — there is nothing to freeze.
    early = client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "lock"}, headers=headers
    )
    assert early.status_code == 400, early.text
    assert "published before it can be locked" in early.json()["detail"]

    client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "publish"}, headers=headers
    )

    again = client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "publish"}, headers=headers
    )
    assert again.status_code == 400, again.text
    assert "already published" in again.json()["detail"]

    locked = client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "lock"}, headers=headers
    )
    assert locked.status_code == 200, locked.text
    assert locked.json()["status"] == "LOCKED"
    assert locked.json()["locked_at"] is not None
    assert locked.json()["locked_by_name"] == "System Administrator"


def test_unlock_is_admin_only_and_leaves_the_lock_stamp_in_place():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    teacher = headers_for(
        setup["faculty"]["email"], setup["faculty"]["generated_password"]
    )
    assessment = make_assessment(headers, setup["assignment_id"])
    seed_marks(assessment["id"], [setup["roster"][0]["id"]], setup["chain"]["section_id"])

    client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "publish"}, headers=headers
    )
    client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "lock"}, headers=headers
    )

    denied = client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "unlock"}, headers=teacher
    )
    assert denied.status_code == 403, denied.text
    assert "administrator" in denied.json()["detail"]

    unlocked = client.patch(
        f"/api/assessments/{assessment['id']}/status",
        json={"action": "unlock", "reason": "Marks correction requested"},
        headers=headers,
    )
    assert unlocked.status_code == 200, unlocked.text
    body = unlocked.json()
    assert body["status"] == "PUBLISHED"
    # The stamp survives: the row still shows that it WAS locked, by whom.
    assert body["locked_at"] is not None
    assert body["locked_by_user_id"] is not None

    not_locked = client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "unlock"}, headers=headers
    )
    assert not_locked.status_code == 400, not_locked.text


# --------------------------------------------------------------------------
# who may do what
# --------------------------------------------------------------------------

def test_faculty_may_manage_their_own_class_only():
    headers = admin_headers()
    mine = setup_class(headers, uuid.uuid4().hex[:6])
    theirs = setup_class(headers, uuid.uuid4().hex[:6])

    teacher = headers_for(mine["faculty"]["email"], mine["faculty"]["generated_password"])

    own = client.post(
        "/api/assessments", json=assessment_payload(mine["assignment_id"]), headers=teacher
    )
    assert own.status_code == 201, own.text
    assert own.json()["created_by_name"] == "Meera Iyer"

    other = client.post(
        "/api/assessments", json=assessment_payload(theirs["assignment_id"]), headers=teacher
    )
    assert other.status_code == 403, other.text
    assert "classes you teach" in other.json()["detail"]


def test_locked_assessment_refuses_faculty_edits_but_not_admin_corrections():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    teacher = headers_for(
        setup["faculty"]["email"], setup["faculty"]["generated_password"]
    )
    assessment = make_assessment(headers, setup["assignment_id"])
    seed_marks(assessment["id"], [setup["roster"][0]["id"]], setup["chain"]["section_id"])

    before = client.patch(
        f"/api/assessments/{assessment['id']}", json={"name": "Internal 1 (revised)"}, headers=teacher
    )
    assert before.status_code == 200, before.text

    client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "publish"}, headers=headers
    )
    client.patch(
        f"/api/assessments/{assessment['id']}/status", json={"action": "lock"}, headers=headers
    )

    blocked = client.patch(
        f"/api/assessments/{assessment['id']}", json={"name": "Internal 1 (again)"}, headers=teacher
    )
    assert blocked.status_code == 403, blocked.text
    assert "locked" in blocked.json()["detail"]

    # Correcting a frozen sheet is exactly what the admin is for.
    corrected = client.patch(
        f"/api/assessments/{assessment['id']}", json={"name": "Internal 1 (corrected)"}, headers=headers
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["name"] == "Internal 1 (corrected)"


def test_students_cannot_reach_the_assessment_endpoints():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    student = setup["roster"][0]
    student_headers = headers_for(student["email"], student["generated_password"])

    listed = client.get("/api/assessments", headers=student_headers)
    assert listed.status_code == 403, listed.text

    created = client.post(
        "/api/assessments", json=assessment_payload(setup["assignment_id"]), headers=student_headers
    )
    assert created.status_code == 403, created.text


def test_faculty_list_is_scoped_and_me_shows_their_own_classes():
    headers = admin_headers()
    mine = setup_class(headers, uuid.uuid4().hex[:6])
    theirs = setup_class(headers, uuid.uuid4().hex[:6])

    make_assessment(headers, mine["assignment_id"], name="Mine")
    make_assessment(headers, theirs["assignment_id"], name="Theirs")

    teacher = headers_for(mine["faculty"]["email"], mine["faculty"]["generated_password"])

    scoped = client.get("/api/assessments", headers=teacher)
    assert scoped.status_code == 200, scoped.text
    names = {item["name"] for item in scoped.json()}
    assert "Mine" in names
    assert "Theirs" not in names

    own = client.get("/api/assessments/me", headers=teacher)
    assert own.status_code == 200, own.text
    assert [item["name"] for item in own.json()] == ["Mine"]

    # The admin sees both.
    everything = client.get("/api/assessments", headers=headers)
    all_names = {item["name"] for item in everything.json()}
    assert {"Mine", "Theirs"} <= all_names


def test_assessment_from_another_department_is_not_readable_by_id():
    headers = admin_headers()
    mine = setup_class(headers, uuid.uuid4().hex[:6])
    theirs = setup_class(headers, uuid.uuid4().hex[:6])
    other = make_assessment(headers, theirs["assignment_id"])

    teacher = headers_for(mine["faculty"]["email"], mine["faculty"]["generated_password"])
    response = client.get(f"/api/assessments/{other['id']}", headers=teacher)
    assert response.status_code == 403, response.text


# --------------------------------------------------------------------------
# entry progress on a list row
# --------------------------------------------------------------------------

def test_progress_counts_come_back_on_the_row():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=3)
    assessment = make_assessment(headers, setup["assignment_id"], max_marks=50)

    fresh = client.get(f"/api/assessments/{assessment['id']}", headers=headers).json()
    assert fresh["total_students"] == 3
    assert fresh["entered_count"] == 0
    assert fresh["pending_count"] == 3
    assert fresh["is_complete"] is False

    seed_marks(
        assessment["id"],
        [student["id"] for student in setup["roster"][:2]],
        setup["chain"]["section_id"],
        marks=[45.0, 10.0],
    )

    partial = client.get(f"/api/assessments/{assessment['id']}", headers=headers).json()
    assert partial["total_students"] == 3
    assert partial["entered_count"] == 2
    assert partial["pending_count"] == 1
    assert partial["is_complete"] is False
    assert partial["average_marks"] == 27.5
    assert partial["average_percent"] == 55.0
    assert partial["highest_marks"] == 45.0
    assert partial["lowest_marks"] == 10.0
    # Pass mark defaults to 20 of 50.
    assert partial["pass_count"] == 1
    assert partial["fail_count"] == 1


# --------------------------------------------------------------------------
# deletion, and the history it must not take with it
# --------------------------------------------------------------------------

def test_delete_with_marks_needs_force_and_states_the_count():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=2)
    assessment = make_assessment(headers, setup["assignment_id"])
    seed_marks(
        assessment["id"],
        [student["id"] for student in setup["roster"]],
        setup["chain"]["section_id"],
    )

    blocked = client.delete(f"/api/assessments/{assessment['id']}", headers=headers)
    assert blocked.status_code == 409, blocked.text
    assert "2 mark record(s)" in blocked.json()["detail"]

    forced = client.delete(
        f"/api/assessments/{assessment['id']}", params={"force": True}, headers=headers
    )
    assert forced.status_code == 204, forced.text
    assert client.get(f"/api/assessments/{assessment['id']}", headers=headers).status_code == 404


def test_delete_is_admin_only():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])
    teacher = headers_for(
        setup["faculty"]["email"], setup["faculty"]["generated_password"]
    )
    assessment = make_assessment(headers, setup["assignment_id"])

    response = client.delete(f"/api/assessments/{assessment['id']}", headers=teacher)
    assert response.status_code == 403, response.text


def test_empty_assessment_deletes_cleanly():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])
    assessment = make_assessment(headers, setup["assignment_id"])

    response = client.delete(f"/api/assessments/{assessment['id']}", headers=headers)
    assert response.status_code == 204, response.text


def test_deleting_a_section_cannot_destroy_exam_history():
    """The structural guard.

    Section cascades delete-orphan into teaching assignments, which cascade
    into timetable entries. If assessments were wired into that chain, removing
    a section would silently destroy every mark it ever received.
    """
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    assessment = make_assessment(headers, setup["assignment_id"])
    seed_marks(assessment["id"], [setup["roster"][0]["id"]], setup["chain"]["section_id"])

    blocked = client.delete(
        f"/api/sections/{setup['chain']['section_id']}", headers=headers
    )
    assert blocked.status_code == 409, blocked.text
    assert "assessment(s) on record" in blocked.json()["detail"]

    # And the assessment is still there.
    assert client.get(f"/api/assessments/{assessment['id']}", headers=headers).status_code == 200


def test_deleting_an_assignment_with_assessments_is_refused():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6])
    make_assessment(headers, setup["assignment_id"])

    response = client.delete(
        f"/api/teaching-assignments/{setup['assignment_id']}", headers=headers
    )
    assert response.status_code == 409, response.text
    assert "assessment(s) on record" in response.json()["detail"]


# --------------------------------------------------------------------------
# options
# --------------------------------------------------------------------------

def test_options_expose_the_policy_constants():
    headers = admin_headers()
    response = client.get("/api/assessments/options", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["types"][0] == "INTERNAL"
    assert body["statuses"] == ["DRAFT", "PUBLISHED", "LOCKED"]
    assert body["counted_statuses"] == ["PUBLISHED", "LOCKED"]
    assert body["default_status"] == "DRAFT"
    assert body["max_total_weightage"] == 100.0
    assert body["pass_percent"] == 40.0
    assert body["attendance_flag_threshold"] == 75.0

    top = body["grade_scale"][0]
    assert top["letter"] == "O"
    assert top["grade_point"] == 10.0
    assert body["grade_scale"][-1]["letter"] == "F"
