"""Timetable module.

The bulk of these tests are about the three clash rules, because a timetable
that lets a lecturer be in two rooms at once is worse than no timetable.
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


def build_hierarchy(headers, suffix, room=None):
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
            "room_number": room or f"R-{suffix}",
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


def make_section(headers, semester_id, code, room=None):
    response = client.post(
        "/api/sections",
        json={
            "semester_id": semester_id,
            "name": f"Section {code}",
            "code": code,
            "capacity": 60,
            "room_number": room or f"R-{code}-{uuid.uuid4().hex[:4]}",
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
        "faculty_id": f"FACTT{suffix}",
        "department_id": department_id,
        "first_name": "Rahul",
        "last_name": "Sharma",
        "email": f"tt.{suffix}@college.edu",
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


def teaching_slots(headers, count=3):
    """The seeded periods that are not breaks."""
    response = client.get("/api/time-slots", headers=headers, params={"is_active": True})
    assert response.status_code == 200, response.text
    slots = [item for item in response.json() if not item["is_break"]]
    assert len(slots) >= count, "the default schedule should seed enough periods"
    return slots[:count]


def break_slot(headers):
    response = client.get("/api/time-slots", headers=headers)
    assert response.status_code == 200
    breaks = [item for item in response.json() if item["is_break"]]
    assert breaks, "the default schedule should seed a break"
    return breaks[0]


def entry_payload(assignment_id, slot_id, day=0, **overrides):
    payload = {
        "teaching_assignment_id": assignment_id,
        "day_of_week": day,
        "time_slot_id": slot_id,
        "room_number": None,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def setup_scheduled(headers, suffix, room=None):
    """A hierarchy, a subject, a faculty member and the assignment joining them."""
    chain = build_hierarchy(headers, suffix, room=room)
    subject_id = make_subject(headers, suffix, chain)
    faculty = make_faculty(headers, suffix, chain["department_id"])
    assignment_id = make_assignment(headers, faculty["id"], subject_id, chain["section_id"])
    return chain, subject_id, faculty, assignment_id


# --------------------------------------------------------------------------
# time slots
# --------------------------------------------------------------------------

def test_default_bell_schedule_is_seeded():
    headers = admin_headers()
    response = client.get("/api/time-slots", headers=headers)
    assert response.status_code == 200, response.text
    slots = response.json()

    assert len(slots) >= 8
    assert slots == sorted(slots, key=lambda item: item["period_number"])
    assert any(item["is_break"] for item in slots)

    first = slots[0]
    assert first["label"] == "09:00 – 09:50"
    assert first["duration_minutes"] == 50


def test_overlapping_period_is_rejected():
    headers = admin_headers()
    response = client.post(
        "/api/time-slots",
        json={
            "period_number": 15,
            "name": "Clashing period",
            "start_time": "09:30:00",
            "end_time": "10:10:00",
            "is_break": False,
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "overlaps" in response.json()["detail"].lower()


def test_period_must_end_after_it_starts():
    headers = admin_headers()
    response = client.post(
        "/api/time-slots",
        json={
            "period_number": 16,
            "name": "Backwards",
            "start_time": "11:00:00",
            "end_time": "10:00:00",
            "is_break": False,
            "is_active": True,
        },
        headers=headers,
    )
    assert response.status_code == 400, response.text


def test_time_slot_in_use_cannot_be_deleted():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    _, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    created = client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    )
    assert created.status_code == 201, created.text

    response = client.delete(f"/api/time-slots/{slot['id']}", headers=headers)
    assert response.status_code == 409, response.text
    assert "scheduled" in response.json()["detail"].lower()


# --------------------------------------------------------------------------
# scheduling a class
# --------------------------------------------------------------------------

def test_create_entry_derives_its_context_from_the_assignment():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    response = client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"], day=2), headers=headers
    )
    assert response.status_code == 201, response.text
    body = response.json()

    # Never sent by the client — resolved from the teaching assignment.
    assert body["faculty_id"] == faculty["id"]
    assert body["section_id"] == chain["section_id"]
    assert body["semester_id"] == chain["semester_id"]

    assert body["subject_id"] == subject_id
    assert body["subject_code"] == f"SUB{suffix}".upper()
    assert body["faculty_name"] == "Rahul Sharma"
    assert body["day_of_week"] == 2
    assert body["day_name"] == "Wednesday"
    assert body["period_number"] == slot["period_number"]
    assert body["start_time"] == slot["start_time"][:5]
    assert body["course_id"] == chain["course_id"]
    assert body["department_id"] == chain["department_id"]
    assert body["academic_year_name"] == f"AY-{suffix}"

    # A blank room falls back to the section's own classroom.
    assert body["room_number"] == f"R-{suffix}"
    assert body["is_relocated"] is False


def test_blank_room_falls_back_and_an_override_marks_the_class_relocated():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    _, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    response = client.post(
        "/api/timetable",
        json=entry_payload(assignment_id, slot["id"], room_number=f"LAB-{suffix}"),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["room_number"] == f"LAB-{suffix}"
    assert body["section_room_number"] == f"R-{suffix}"
    assert body["is_relocated"] is True


def test_class_cannot_be_scheduled_in_a_break():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    _, _, _, assignment_id = setup_scheduled(headers, suffix)
    lunch = break_slot(headers)

    response = client.post(
        "/api/timetable", json=entry_payload(assignment_id, lunch["id"]), headers=headers
    )
    assert response.status_code == 400, response.text
    assert "break" in response.json()["detail"].lower()


def test_paused_assignment_cannot_be_scheduled():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    _, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    paused = client.patch(
        f"/api/teaching-assignments/{assignment_id}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert paused.status_code == 200, paused.text

    response = client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    )
    assert response.status_code == 400, response.text
    assert "paused" in response.json()["detail"].lower()


# --------------------------------------------------------------------------
# the three clash rules
# --------------------------------------------------------------------------

def test_section_cannot_attend_two_classes_at_once():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, _, faculty, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    ).status_code == 201

    # A different subject and a different lecturer, but the same section.
    other_subject = make_subject(
        headers, f"{suffix}B", chain, subject_code=f"SUB{suffix}B", name="Operating Systems"
    )
    other_faculty = make_faculty(
        headers,
        f"{suffix}B",
        chain["department_id"],
        faculty_id=f"FACTT{suffix}B",
        email=f"tt.{suffix}b@college.edu",
    )
    other_assignment = make_assignment(
        headers, other_faculty["id"], other_subject, chain["section_id"]
    )

    response = client.post(
        "/api/timetable", json=entry_payload(other_assignment, slot["id"]), headers=headers
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "this section already has" in detail.lower()
    # The message has to name what to move.
    assert "Database Management Systems" in detail


def test_faculty_cannot_be_double_booked_across_departments():
    """The likeliest real double-booking, and the one a department-scoped
    check would miss entirely."""
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, _, faculty, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    ).status_code == 201

    # An entirely separate department, teaching the same lecturer's period.
    other_chain = build_hierarchy(headers, f"{suffix}X")
    other_subject = make_subject(
        headers, f"{suffix}X", other_chain, subject_code=f"SUB{suffix}X", name="Thermodynamics"
    )
    cross_assignment = make_assignment(
        headers, faculty["id"], other_subject, other_chain["section_id"]
    )

    response = client.post(
        "/api/timetable", json=entry_payload(cross_assignment, slot["id"]), headers=headers
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "Rahul Sharma" in detail
    assert "already teaches" in detail


def test_room_cannot_hold_two_classes_at_once():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    shared_room = f"HALL-{suffix}"
    _, _, _, assignment_id = setup_scheduled(headers, suffix, room=shared_room)
    slot = teaching_slots(headers)[0]

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    ).status_code == 201

    # A different department and lecturer relocated into the same hall.
    other_chain = build_hierarchy(headers, f"{suffix}Y")
    other_subject = make_subject(
        headers, f"{suffix}Y", other_chain, subject_code=f"SUB{suffix}Y", name="Fluid Mechanics"
    )
    other_faculty = make_faculty(
        headers,
        f"{suffix}Y",
        other_chain["department_id"],
        faculty_id=f"FACTT{suffix}Y",
        email=f"tt.{suffix}y@college.edu",
    )
    other_assignment = make_assignment(
        headers, other_faculty["id"], other_subject, other_chain["section_id"]
    )

    # Typed loosely on purpose: rooms are hand-entered and must still collide.
    response = client.post(
        "/api/timetable",
        json=entry_payload(other_assignment, slot["id"], room_number=f"  hall {suffix}  "),
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "occupied" in response.json()["detail"].lower()


def test_same_room_in_a_different_period_is_fine():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    shared_room = f"HALL-{suffix}"
    _, _, _, assignment_id = setup_scheduled(headers, suffix, room=shared_room)
    slots = teaching_slots(headers, count=2)

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slots[0]["id"]), headers=headers
    ).status_code == 201

    other_chain = build_hierarchy(headers, f"{suffix}Z")
    other_subject = make_subject(
        headers, f"{suffix}Z", other_chain, subject_code=f"SUB{suffix}Z", name="Statics"
    )
    other_faculty = make_faculty(
        headers,
        f"{suffix}Z",
        other_chain["department_id"],
        faculty_id=f"FACTT{suffix}Z",
        email=f"tt.{suffix}z@college.edu",
    )
    other_assignment = make_assignment(
        headers, other_faculty["id"], other_subject, other_chain["section_id"]
    )

    response = client.post(
        "/api/timetable",
        json=entry_payload(other_assignment, slots[1]["id"], room_number=shared_room),
        headers=headers,
    )
    assert response.status_code == 201, response.text


def test_same_period_on_a_different_day_is_fine():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    _, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"], day=0), headers=headers
    ).status_code == 201
    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"], day=1), headers=headers
    ).status_code == 201


def test_editing_an_entry_does_not_clash_with_itself():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    _, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    created = client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    )
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]

    response = client.put(
        f"/api/timetable/{entry_id}",
        json=entry_payload(assignment_id, slot["id"], room_number=f"LAB-{suffix}"),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["room_number"] == f"LAB-{suffix}"


def test_a_deactivated_class_still_holds_its_cell():
    """Matching the teaching assignment rule: the database constraint does not
    filter on is_active either, so the admin is pointed at the existing row."""
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    created = client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    )
    assert created.status_code == 201, created.text

    paused = client.patch(
        f"/api/timetable/{created.json()['id']}/status", json={"is_active": False}, headers=headers
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["is_active"] is False

    other_subject = make_subject(
        headers, f"{suffix}D", chain, subject_code=f"SUB{suffix}D", name="Compiler Design"
    )
    other_faculty = make_faculty(
        headers,
        f"{suffix}D",
        chain["department_id"],
        faculty_id=f"FACTT{suffix}D",
        email=f"tt.{suffix}d@college.edu",
    )
    other_assignment = make_assignment(
        headers, other_faculty["id"], other_subject, chain["section_id"]
    )

    response = client.post(
        "/api/timetable", json=entry_payload(other_assignment, slot["id"]), headers=headers
    )
    assert response.status_code == 409, response.text


# --------------------------------------------------------------------------
# copy day
# --------------------------------------------------------------------------

def test_copy_day_duplicates_a_day_and_reports_what_it_skipped():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, _, _, assignment_id = setup_scheduled(headers, suffix)
    slots = teaching_slots(headers, count=2)

    second_subject = make_subject(
        headers, f"{suffix}C", chain, subject_code=f"SUB{suffix}C", name="Computer Networks"
    )
    second_faculty = make_faculty(
        headers,
        f"{suffix}C",
        chain["department_id"],
        faculty_id=f"FACTT{suffix}C",
        email=f"tt.{suffix}c@college.edu",
    )
    second_assignment = make_assignment(
        headers, second_faculty["id"], second_subject, chain["section_id"]
    )

    # Monday: two periods.
    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slots[0]["id"], day=0), headers=headers
    ).status_code == 201
    assert client.post(
        "/api/timetable",
        json=entry_payload(second_assignment, slots[1]["id"], day=0),
        headers=headers,
    ).status_code == 201

    # Tuesday already has the first period filled.
    assert client.post(
        "/api/timetable",
        json=entry_payload(second_assignment, slots[0]["id"], day=1),
        headers=headers,
    ).status_code == 201

    response = client.post(
        "/api/timetable/copy-day",
        json={"section_id": chain["section_id"], "from_day": 0, "to_day": 1},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()

    # The free period is copied; the occupied one is reported, not fatal.
    assert len(body["created"]) == 1
    assert body["created"][0]["day_of_week"] == 1
    assert body["created"][0]["time_slot_id"] == slots[1]["id"]

    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["time_slot_id"] == slots[0]["id"]
    assert "Computer Networks" in body["skipped"][0]["reason"]


def test_copy_day_rejects_copying_onto_itself():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"], day=0), headers=headers
    ).status_code == 201

    response = client.post(
        "/api/timetable/copy-day",
        json={"section_id": chain["section_id"], "from_day": 0, "to_day": 0},
        headers=headers,
    )
    assert response.status_code == 400, response.text


def test_copy_day_needs_something_to_copy():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, _, _, _ = setup_scheduled(headers, suffix)

    response = client.post(
        "/api/timetable/copy-day",
        json={"section_id": chain["section_id"], "from_day": 3, "to_day": 4},
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "Thursday" in response.json()["detail"]


# --------------------------------------------------------------------------
# coverage
# --------------------------------------------------------------------------

def test_coverage_reads_the_subject_hours_nothing_else_uses():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    # 3 lecture + 1 tutorial + 2 practical = 6 periods a week.
    subject_id = make_subject(
        headers, suffix, chain, lecture_hours=3, tutorial_hours=1, practical_hours=2
    )
    faculty = make_faculty(headers, suffix, chain["department_id"])
    assignment_id = make_assignment(headers, faculty["id"], subject_id, chain["section_id"])
    slots = teaching_slots(headers, count=2)

    empty = client.get(
        "/api/timetable/coverage", params={"section_id": chain["section_id"]}, headers=headers
    )
    assert empty.status_code == 200, empty.text
    body = empty.json()
    assert body["total_required"] == 6
    assert body["total_scheduled"] == 0
    assert body["subjects"][0]["status"] == "UNSCHEDULED"
    assert body["subjects"][0]["remaining_periods"] == 6

    for index, slot in enumerate(slots):
        assert client.post(
            "/api/timetable",
            json=entry_payload(assignment_id, slot["id"], day=index),
            headers=headers,
        ).status_code == 201

    partial = client.get(
        "/api/timetable/coverage", params={"section_id": chain["section_id"]}, headers=headers
    ).json()
    subject = partial["subjects"][0]
    assert subject["required_periods"] == 6
    assert subject["scheduled_periods"] == 2
    assert subject["remaining_periods"] == 4
    assert subject["status"] == "UNDER_SCHEDULED"
    assert subject["faculty_name"] == "Rahul Sharma"
    assert partial["total_scheduled"] == 2


def test_coverage_flags_an_over_scheduled_subject():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)
    subject_id = make_subject(
        headers, suffix, chain, lecture_hours=1, tutorial_hours=0, practical_hours=0
    )
    faculty = make_faculty(headers, suffix, chain["department_id"])
    assignment_id = make_assignment(headers, faculty["id"], subject_id, chain["section_id"])
    slots = teaching_slots(headers, count=2)

    for index, slot in enumerate(slots):
        assert client.post(
            "/api/timetable",
            json=entry_payload(assignment_id, slot["id"], day=index),
            headers=headers,
        ).status_code == 201

    body = client.get(
        "/api/timetable/coverage", params={"section_id": chain["section_id"]}, headers=headers
    ).json()
    assert body["subjects"][0]["status"] == "OVER_SCHEDULED"
    assert body["subjects"][0]["remaining_periods"] == 0


# --------------------------------------------------------------------------
# personal timetables and access control
# --------------------------------------------------------------------------

def test_faculty_me_includes_their_cross_department_classes():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, _, faculty, assignment_id = setup_scheduled(headers, suffix)
    slots = teaching_slots(headers, count=2)

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slots[0]["id"], day=0), headers=headers
    ).status_code == 201

    other_chain = build_hierarchy(headers, f"{suffix}M")
    other_subject = make_subject(
        headers, f"{suffix}M", other_chain, subject_code=f"SUB{suffix}M", name="Applied Maths"
    )
    cross_assignment = make_assignment(
        headers, faculty["id"], other_subject, other_chain["section_id"]
    )
    assert client.post(
        "/api/timetable",
        json=entry_payload(cross_assignment, slots[1]["id"], day=0),
        headers=headers,
    ).status_code == 201

    login = client.post(
        "/api/auth/login",
        json={"email": faculty["email"], "password": faculty["generated_password"]},
    )
    assert login.status_code == 200, login.text
    faculty_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/timetable/me", headers=faculty_headers)
    assert response.status_code == 200, response.text
    mine = response.json()
    assert len(mine) == 2
    assert {item["subject_name"] for item in mine} == {
        "Database Management Systems",
        "Applied Maths",
    }

    # The department-scoped list hides the cross-department class.
    scoped = client.get("/api/timetable", headers=faculty_headers)
    assert scoped.status_code == 200, scoped.text
    assert {item["subject_name"] for item in scoped.json()} == {"Database Management Systems"}

    monday_only = client.get(
        "/api/timetable/me", params={"day_of_week": 1}, headers=faculty_headers
    )
    assert monday_only.status_code == 200
    assert monday_only.json() == []


def test_student_me_returns_their_own_sections_timetable():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"], day=0), headers=headers
    ).status_code == 201

    student = client.post(
        "/api/students",
        json={
            "student_id": f"STUTT{suffix}",
            "first_name": "Test",
            "last_name": "Student",
            "email": f"ttstudent.{suffix}@college.edu",
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
        json={
            "email": student.json()["email"],
            "password": student.json()["generated_password"],
        },
    )
    assert login.status_code == 200, login.text
    student_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/timetable/me", headers=student_headers)
    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["subject_name"] == "Database Management Systems"

    # Students still cannot browse the whole college.
    assert client.get("/api/timetable", headers=student_headers).status_code == 403


def test_admin_has_no_personal_timetable():
    headers = admin_headers()
    response = client.get("/api/timetable/me", headers=headers)
    assert response.status_code == 400, response.text
    assert "filter" in response.json()["detail"].lower()


def test_faculty_cannot_write_the_timetable():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    _, _, faculty, assignment_id = setup_scheduled(headers, suffix)
    slots = teaching_slots(headers, count=2)

    created = client.post(
        "/api/timetable", json=entry_payload(assignment_id, slots[0]["id"]), headers=headers
    )
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]

    login = client.post(
        "/api/auth/login",
        json={"email": faculty["email"], "password": faculty["generated_password"]},
    )
    assert login.status_code == 200, login.text
    faculty_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.post(
        "/api/timetable",
        json=entry_payload(assignment_id, slots[1]["id"]),
        headers=faculty_headers,
    ).status_code == 403
    assert client.put(
        f"/api/timetable/{entry_id}",
        json=entry_payload(assignment_id, slots[1]["id"]),
        headers=faculty_headers,
    ).status_code == 403
    assert client.patch(
        f"/api/timetable/{entry_id}/status", json={"is_active": False}, headers=faculty_headers
    ).status_code == 403
    assert client.delete(f"/api/timetable/{entry_id}", headers=faculty_headers).status_code == 403
    assert client.post(
        "/api/time-slots",
        json={
            "period_number": 18,
            "name": "Sneaky",
            "start_time": "18:00:00",
            "end_time": "19:00:00",
            "is_break": False,
            "is_active": True,
        },
        headers=faculty_headers,
    ).status_code == 403


# --------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------

def test_deleting_a_section_takes_its_scheduled_classes_with_it():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain, subject_id, faculty, _ = setup_scheduled(headers, suffix)
    spare_section = make_section(headers, chain["semester_id"], "B")
    spare_assignment = make_assignment(headers, faculty["id"], subject_id, spare_section)
    slot = teaching_slots(headers)[0]

    created = client.post(
        "/api/timetable", json=entry_payload(spare_assignment, slot["id"], day=4), headers=headers
    )
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]

    # Sections guard against deletion while assignments exist, so the
    # assignment goes first; the class must not outlive it.
    assert client.delete(
        f"/api/teaching-assignments/{spare_assignment}", headers=headers
    ).status_code == 204
    assert client.get(f"/api/timetable/{entry_id}", headers=headers).status_code == 404


def test_delete_entry_frees_the_cell():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    _, _, _, assignment_id = setup_scheduled(headers, suffix)
    slot = teaching_slots(headers)[0]

    created = client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    )
    assert created.status_code == 201, created.text

    assert client.delete(
        f"/api/timetable/{created.json()['id']}", headers=headers
    ).status_code == 204

    assert client.post(
        "/api/timetable", json=entry_payload(assignment_id, slot["id"]), headers=headers
    ).status_code == 201
