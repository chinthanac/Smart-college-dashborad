"""Attendance module.

Most of these tests are about the two ways a register can lie: by counting a
class that never happened, and by quietly losing a student. The date rules and
the roster rules get the most attention for that reason.
"""

import uuid
from datetime import date, timedelta

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


def date_for_weekday(day_of_week, weeks_back=0):
    """The most recent past-or-today date falling on that weekday."""
    today = date.today()
    delta = (today.weekday() - day_of_week) % 7
    return today - timedelta(days=delta + 7 * weeks_back)


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
            "start_date": "2026-01-01",
            "end_date": "2027-12-31",
            "is_current": False,
        },
        headers=headers,
    )
    assert academic_year.status_code == 201, academic_year.text
    academic_year_id = academic_year.json()["id"]

    # Wide enough that "today" always falls inside it, whenever the suite runs.
    semester = client.post(
        "/api/semesters",
        json={
            "course_id": course_id,
            "academic_year_id": academic_year_id,
            "semester_number": 5,
            "name": f"Semester 5 {suffix}",
            "start_date": str(date.today() - timedelta(days=200)),
            "end_date": str(date.today() + timedelta(days=200)),
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
        "faculty_id": f"FACAT{suffix}",
        "department_id": department_id,
        "first_name": "Priya",
        "last_name": "Nair",
        "email": f"at.{suffix}@college.edu",
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
        "first_name": "Amit",
        "last_name": "Verma",
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


def teaching_slots(headers, count=3):
    response = client.get("/api/time-slots", headers=headers, params={"is_active": True})
    assert response.status_code == 200, response.text
    slots = [item for item in response.json() if not item["is_break"]]
    assert len(slots) >= count
    return slots[:count]


def schedule(headers, assignment_id, slot_id, day=0, **overrides):
    payload = {
        "teaching_assignment_id": assignment_id,
        "day_of_week": day,
        "time_slot_id": slot_id,
        "room_number": None,
        "is_active": True,
    }
    payload.update(overrides)
    response = client.post("/api/timetable", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def setup_class(headers, suffix, students=2, day=0):
    """A scheduled class with a roster, ready to mark."""
    chain = build_hierarchy(headers, suffix)
    subject_id = make_subject(headers, suffix, chain)
    faculty = make_faculty(headers, suffix, chain["department_id"])
    assignment_id = make_assignment(headers, faculty["id"], subject_id, chain["section_id"])
    slot = teaching_slots(headers)[0]
    entry_id = schedule(headers, assignment_id, slot["id"], day=day)

    roster = [
        make_student(headers, f"{suffix}{index}", chain, student_id=f"STU{suffix}{index}")
        for index in range(students)
    ]
    return {
        "chain": chain,
        "subject_id": subject_id,
        "faculty": faculty,
        "assignment_id": assignment_id,
        "entry_id": entry_id,
        "slot": slot,
        "roster": roster,
        "day": day,
    }


def get_sheet(headers, entry_id, class_date):
    return client.get(
        "/api/attendance/sheet",
        headers=headers,
        params={"timetable_entry_id": entry_id, "class_date": str(class_date)},
    )


def save_sheet(headers, entry_id, class_date, records, **overrides):
    payload = {
        "timetable_entry_id": entry_id,
        "class_date": str(class_date),
        "session_status": "HELD",
        "records": records,
    }
    payload.update(overrides)
    return client.post("/api/attendance/sheet", json=payload, headers=headers)


# --------------------------------------------------------------------------
# options
# --------------------------------------------------------------------------

def test_options_lists_every_status_the_service_accepts():
    response = client.get("/api/attendance/options")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["statuses"] == ["PRESENT", "ABSENT", "LATE", "EXCUSED"]
    assert body["present_statuses"] == ["PRESENT", "LATE"]
    assert body["session_statuses"] == ["HELD", "CANCELLED"]


# --------------------------------------------------------------------------
# the sheet
# --------------------------------------------------------------------------

def test_opening_a_sheet_prefills_the_sections_active_students():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=3)

    response = get_sheet(headers, setup["entry_id"], date_for_weekday(setup["day"]))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["sheet_state"] == "DRAFT"
    assert len(body["records"]) == 3
    assert {r["status"] for r in body["records"]} == {"PRESENT"}
    # Roll-number order is what an attendance sheet is read in.
    codes = [r["student_code"] for r in body["records"]]
    assert codes == sorted(codes)


def test_opening_a_sheet_does_not_create_a_session():
    """The session row is the denominator of every percentage — browsing must
    never manufacture one."""
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)
    class_date = date_for_weekday(setup["day"])

    assert get_sheet(headers, setup["entry_id"], class_date).json()["session"] is None
    get_sheet(headers, setup["entry_id"], class_date)

    sessions = client.get(
        "/api/attendance/sessions",
        headers=headers,
        params={"timetable_entry_id": setup["entry_id"]},
    )
    assert sessions.json() == []


def test_inactive_students_are_left_off_a_new_sheet():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    dropped = setup["roster"][0]

    assert (
        client.patch(
            f"/api/students/{dropped['id']}/status",
            json={"status": "INACTIVE"},
            headers=headers,
        ).status_code
        == 200
    )

    body = get_sheet(headers, setup["entry_id"], date_for_weekday(setup["day"])).json()
    assert [r["student_id"] for r in body["records"]] == [setup["roster"][1]["id"]]


def test_a_section_with_no_students_gives_a_locked_sheet_not_a_crash():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=0)

    body = get_sheet(headers, setup["entry_id"], date_for_weekday(setup["day"])).json()
    assert body["records"] == []
    assert body["editable"] is False
    assert "no active students" in body["locked_reason"].lower()


# --------------------------------------------------------------------------
# date rules
# --------------------------------------------------------------------------

def test_marking_a_date_that_is_not_the_classes_day_is_rejected():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, day=0)  # Monday

    response = get_sheet(headers, setup["entry_id"], date_for_weekday(3))  # a Thursday
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    # The message has to name both days, or the user cannot tell what is wrong.
    assert "Monday" in detail and "Thursday" in detail


def test_attendance_cannot_be_marked_for_a_future_date():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)
    future = date_for_weekday(setup["day"]) + timedelta(days=7)

    response = get_sheet(headers, setup["entry_id"], future)
    assert response.status_code == 400, response.text
    assert "has not happened yet" in response.json()["detail"]


def test_faculty_cannot_backdate_beyond_the_window_but_an_admin_can():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)
    faculty_headers = headers_for(
        setup["faculty"]["email"], setup["faculty"]["generated_password"]
    )
    old = date_for_weekday(setup["day"], weeks_back=8)  # ~56 days back

    refused = get_sheet(faculty_headers, setup["entry_id"], old)
    assert refused.status_code == 400, refused.text
    assert "30 days" in refused.json()["detail"]

    allowed = get_sheet(headers, setup["entry_id"], old)
    assert allowed.status_code == 200, allowed.text


def test_a_date_outside_the_semester_is_rejected():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)
    # The hierarchy's semester spans +/- 200 days, so reach well beyond it.
    far = date_for_weekday(setup["day"], weeks_back=40)

    response = get_sheet(headers, setup["entry_id"], far)
    assert response.status_code == 400, response.text
    assert "outside" in response.json()["detail"].lower()


# --------------------------------------------------------------------------
# saving
# --------------------------------------------------------------------------

def test_saving_a_sheet_records_who_marked_it_and_derives_the_class_from_the_entry():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    class_date = date_for_weekday(setup["day"])

    response = save_sheet(
        headers,
        setup["entry_id"],
        class_date,
        [
            {"student_id": setup["roster"][0]["id"], "status": "PRESENT"},
            {"student_id": setup["roster"][1]["id"], "status": "ABSENT"},
        ],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    session = body["session"]

    assert body["sheet_state"] == "MARKED"
    assert session["marked_by_role"] == "ADMIN"
    # Identity is copied from the entry, never taken from the caller.
    assert session["subject_id"] == setup["subject_id"]
    assert session["section_id"] == setup["chain"]["section_id"]
    assert session["faculty_id"] == setup["faculty"]["id"]
    assert session["day_of_week"] == setup["day"]
    assert body["attendance_percentage"] == 50.0


def test_saving_the_same_sheet_twice_corrects_it_rather_than_duplicating():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    class_date = date_for_weekday(setup["day"])
    first, second = setup["roster"]

    save_sheet(
        headers,
        setup["entry_id"],
        class_date,
        [
            {"student_id": first["id"], "status": "PRESENT"},
            {"student_id": second["id"], "status": "ABSENT"},
        ],
    )
    response = save_sheet(
        headers,
        setup["entry_id"],
        class_date,
        [
            {"student_id": first["id"], "status": "PRESENT"},
            {"student_id": second["id"], "status": "PRESENT"},
        ],
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["records"]) == 2
    assert body["attendance_percentage"] == 100.0

    sessions = client.get(
        "/api/attendance/sessions",
        headers=headers,
        params={"timetable_entry_id": setup["entry_id"]},
    ).json()
    assert len(sessions) == 1


def test_excused_is_removed_from_the_denominator_and_late_counts_as_present():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=3)
    class_date = date_for_weekday(setup["day"])
    present, late, excused = setup["roster"]

    response = save_sheet(
        headers,
        setup["entry_id"],
        class_date,
        [
            {"student_id": present["id"], "status": "PRESENT"},
            {"student_id": late["id"], "status": "LATE"},
            {"student_id": excused["id"], "status": "EXCUSED"},
        ],
    )
    body = response.json()

    assert body["present_count"] == 2  # PRESENT + LATE
    assert body["countable_count"] == 2  # EXCUSED left the denominator
    assert body["attendance_percentage"] == 100.0


def test_a_student_cannot_be_submitted_twice_on_one_sheet():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)
    student = setup["roster"][0]

    response = save_sheet(
        headers,
        setup["entry_id"],
        date_for_weekday(setup["day"]),
        [
            {"student_id": student["id"], "status": "PRESENT"},
            {"student_id": student["id"], "status": "ABSENT"},
        ],
    )
    assert response.status_code == 400, response.text
    # The message has to name who, or the user cannot find the duplicate.
    assert "Amit Verma" in response.json()["detail"]
    assert "twice" in response.json()["detail"]


def test_a_student_from_another_section_cannot_be_marked():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)
    other = setup_class(headers, uuid.uuid4().hex[:6])

    response = save_sheet(
        headers,
        setup["entry_id"],
        date_for_weekday(setup["day"]),
        [{"student_id": other["roster"][0]["id"], "status": "PRESENT"}],
    )
    assert response.status_code == 400, response.text
    assert "not in" in response.json()["detail"].lower()


def test_an_unknown_status_is_refused():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)

    response = save_sheet(
        headers,
        setup["entry_id"],
        date_for_weekday(setup["day"]),
        [{"student_id": setup["roster"][0]["id"], "status": "MAYBE"}],
    )
    assert response.status_code == 400, response.text
    assert "PRESENT" in response.json()["detail"]


def test_a_student_added_after_the_sheet_was_marked_appears_as_unmarked():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    class_date = date_for_weekday(setup["day"])

    save_sheet(
        headers,
        setup["entry_id"],
        class_date,
        [{"student_id": setup["roster"][0]["id"], "status": "PRESENT"}],
    )
    joiner = make_student(
        headers, f"{suffix}late", setup["chain"], student_id=f"STUZZ{suffix}"
    )

    body = get_sheet(headers, setup["entry_id"], class_date).json()
    ids = [r["student_id"] for r in body["records"]]
    assert joiner["id"] in ids, "a student admitted later must still be markable"
    joiner_row = next(r for r in body["records"] if r["student_id"] == joiner["id"])
    assert joiner_row["id"] is None, "their row is a draft, not a saved record"


# --------------------------------------------------------------------------
# cancelling
# --------------------------------------------------------------------------

def test_a_cancelled_class_needs_a_reason_and_stores_no_records():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    class_date = date_for_weekday(setup["day"])

    refused = save_sheet(
        headers, setup["entry_id"], class_date, [], session_status="CANCELLED"
    )
    assert refused.status_code == 400, refused.text
    assert "why" in refused.json()["detail"].lower()

    response = save_sheet(
        headers,
        setup["entry_id"],
        class_date,
        [],
        session_status="CANCELLED",
        cancel_reason="Faculty on college duty",
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["sheet_state"] == "CANCELLED"
    # A class that never happened shows nobody present — not a full roster of
    # default-PRESENT drafts.
    assert body["records"] == []
    assert body["present_count"] == 0
    assert body["attendance_percentage"] == 0.0


def test_a_cancelled_session_is_left_out_of_the_percentage():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    student = setup["roster"][0]

    held = date_for_weekday(setup["day"])
    cancelled = date_for_weekday(setup["day"], weeks_back=1)

    save_sheet(headers, setup["entry_id"], held, [{"student_id": student["id"], "status": "PRESENT"}])
    save_sheet(
        headers,
        setup["entry_id"],
        cancelled,
        [],
        session_status="CANCELLED",
        cancel_reason="Public holiday",
    )

    report = client.get(
        "/api/attendance/report/student",
        headers=headers,
        params={"student_id": student["id"]},
    ).json()

    assert report["overall_countable"] == 1, "the cancelled class must not count"
    assert report["overall_percentage"] == 100.0


def test_cancelling_an_already_marked_session_clears_its_records():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    class_date = date_for_weekday(setup["day"])

    saved = save_sheet(
        headers,
        setup["entry_id"],
        class_date,
        [{"student_id": s["id"], "status": "PRESENT"} for s in setup["roster"]],
    ).json()
    session_id = saved["session"]["id"]

    response = client.patch(
        f"/api/attendance/sessions/{session_id}/status",
        json={"session_status": "CANCELLED", "cancel_reason": "Strike"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_students"] == 0


# --------------------------------------------------------------------------
# who may mark
# --------------------------------------------------------------------------

def test_a_faculty_member_cannot_mark_another_lecturers_class():
    headers = admin_headers()
    mine = setup_class(headers, uuid.uuid4().hex[:6])
    theirs = setup_class(headers, uuid.uuid4().hex[:6])

    intruder = headers_for(
        mine["faculty"]["email"], mine["faculty"]["generated_password"]
    )
    class_date = date_for_weekday(theirs["day"])

    read = get_sheet(intruder, theirs["entry_id"], class_date)
    assert read.status_code == 403, read.text
    assert "your own classes" in read.json()["detail"]

    write = save_sheet(
        intruder,
        theirs["entry_id"],
        class_date,
        [{"student_id": theirs["roster"][0]["id"], "status": "ABSENT"}],
    )
    assert write.status_code == 403, write.text


def test_a_faculty_member_can_mark_their_own_class():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    teacher = headers_for(
        setup["faculty"]["email"], setup["faculty"]["generated_password"]
    )

    response = save_sheet(
        teacher,
        setup["entry_id"],
        date_for_weekday(setup["day"]),
        [{"student_id": s["id"], "status": "PRESENT"} for s in setup["roster"]],
    )
    assert response.status_code == 200, response.text
    assert response.json()["session"]["marked_by_role"] == "FACULTY"


def test_admin_can_correct_a_sheet_a_faculty_member_saved():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    student = setup["roster"][0]
    teacher = headers_for(
        setup["faculty"]["email"], setup["faculty"]["generated_password"]
    )
    class_date = date_for_weekday(setup["day"])

    save_sheet(teacher, setup["entry_id"], class_date, [{"student_id": student["id"], "status": "ABSENT"}])
    corrected = save_sheet(
        headers, setup["entry_id"], class_date, [{"student_id": student["id"], "status": "PRESENT"}]
    )

    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["session"]["marked_by_role"] == "ADMIN"
    assert corrected.json()["attendance_percentage"] == 100.0


def test_a_student_cannot_mark_attendance():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix)
    student = setup["roster"][0]
    student_headers = headers_for(student["email"], student["generated_password"])

    response = save_sheet(
        student_headers,
        setup["entry_id"],
        date_for_weekday(setup["day"]),
        [{"student_id": student["id"], "status": "PRESENT"}],
    )
    assert response.status_code == 403, response.text


def test_a_paused_class_cannot_open_a_new_sheet_but_keeps_its_old_ones():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    marked_date = date_for_weekday(setup["day"])

    save_sheet(
        headers, setup["entry_id"], marked_date, [{"student_id": setup["roster"][0]["id"], "status": "PRESENT"}]
    )
    assert (
        client.patch(
            f"/api/timetable/{setup['entry_id']}/status",
            json={"is_active": False},
            headers=headers,
        ).status_code
        == 200
    )

    # A new date is refused...
    fresh = get_sheet(headers, setup["entry_id"], date_for_weekday(setup["day"], weeks_back=1))
    assert fresh.status_code == 400, fresh.text
    assert "paused" in fresh.json()["detail"].lower()

    # ...but a register that already exists stays correctable.
    existing = get_sheet(headers, setup["entry_id"], marked_date)
    assert existing.status_code == 200, existing.text


# --------------------------------------------------------------------------
# a lecturer's day
# --------------------------------------------------------------------------

def test_my_classes_lists_only_the_signed_in_lecturers_classes_for_that_day():
    headers = admin_headers()
    mine = setup_class(headers, uuid.uuid4().hex[:6], day=0)
    setup_class(headers, uuid.uuid4().hex[:6], day=0)  # somebody else's Monday

    teacher = headers_for(mine["faculty"]["email"], mine["faculty"]["generated_password"])
    monday = date_for_weekday(0)

    response = client.get(
        "/api/attendance/my-classes", headers=teacher, params={"class_date": str(monday)}
    )
    assert response.status_code == 200, response.text
    rows = response.json()

    assert [r["timetable_entry_id"] for r in rows] == [mine["entry_id"]]
    assert rows[0]["status"] == "UNMARKED"


def test_my_classes_shows_which_sheets_are_already_marked():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2, day=0)
    teacher = headers_for(setup["faculty"]["email"], setup["faculty"]["generated_password"])
    monday = date_for_weekday(0)

    save_sheet(
        teacher,
        setup["entry_id"],
        monday,
        [
            {"student_id": setup["roster"][0]["id"], "status": "PRESENT"},
            {"student_id": setup["roster"][1]["id"], "status": "ABSENT"},
        ],
    )

    rows = client.get(
        "/api/attendance/my-classes", headers=teacher, params={"class_date": str(monday)}
    ).json()
    row = next(r for r in rows if r["timetable_entry_id"] == setup["entry_id"])

    assert row["status"] == "MARKED"
    assert row["marked"] is True
    assert row["present_count"] == 1
    assert row["total_students"] == 2


def test_admin_has_no_personal_class_list_or_attendance():
    headers = admin_headers()

    classes = client.get("/api/attendance/my-classes", headers=headers)
    assert classes.status_code == 403, classes.text  # faculty-only dependency

    mine = client.get("/api/attendance/me", headers=headers)
    assert mine.status_code == 400, mine.text
    assert "students" in mine.json()["detail"].lower()


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def test_a_student_sees_their_own_per_subject_percentage():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    student = setup["roster"][0]

    save_sheet(
        headers, setup["entry_id"], date_for_weekday(setup["day"]), [{"student_id": student["id"], "status": "PRESENT"}]
    )
    save_sheet(
        headers,
        setup["entry_id"],
        date_for_weekday(setup["day"], weeks_back=1),
        [{"student_id": student["id"], "status": "ABSENT"}],
    )

    student_headers = headers_for(student["email"], student["generated_password"])
    body = client.get("/api/attendance/me", headers=student_headers).json()

    assert body["student_id"] == student["id"]
    assert body["overall_countable"] == 2
    assert body["overall_percentage"] == 50.0
    assert len(body["subjects"]) == 1
    assert body["subjects"][0]["subject_id"] == setup["subject_id"]


def test_a_student_cannot_read_another_students_attendance():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    student_headers = headers_for(
        setup["roster"][0]["email"], setup["roster"][0]["generated_password"]
    )

    response = client.get(
        "/api/attendance/report/student",
        headers=student_headers,
        params={"student_id": setup["roster"][1]["id"]},
    )
    assert response.status_code == 403, response.text


def test_the_section_report_flags_students_below_the_threshold():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    good, poor = setup["roster"]

    for weeks in range(4):
        save_sheet(
            headers,
            setup["entry_id"],
            date_for_weekday(setup["day"], weeks_back=weeks),
            [
                {"student_id": good["id"], "status": "PRESENT"},
                {"student_id": poor["id"], "status": "PRESENT" if weeks == 0 else "ABSENT"},
            ],
        )

    report = client.get(
        "/api/attendance/report/section",
        headers=headers,
        params={"section_id": setup["chain"]["section_id"]},
    ).json()

    assert report["held_sessions"] == 4
    assert report["total_students"] == 2
    assert report["defaulter_count"] == 1

    rows = {r["student_id"]: r for r in report["students"]}
    assert rows[good["id"]]["attendance_percentage"] == 100.0
    assert rows[good["id"]]["status"] == "GOOD"
    assert rows[poor["id"]]["attendance_percentage"] == 25.0
    assert rows[poor["id"]]["status"] == "SHORT"


def test_a_suspended_student_keeps_the_attendance_they_already_earned():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    student = setup["roster"][0]

    save_sheet(
        headers, setup["entry_id"], date_for_weekday(setup["day"]), [{"student_id": student["id"], "status": "PRESENT"}]
    )
    client.patch(
        f"/api/students/{student['id']}/status",
        json={"status": "SUSPENDED"},
        headers=headers,
    )

    report = client.get(
        "/api/attendance/report/student", headers=headers, params={"student_id": student["id"]}
    ).json()
    assert report["overall_countable"] == 1, "history must survive a status change"
    assert report["overall_percentage"] == 100.0


# --------------------------------------------------------------------------
# history protection
# --------------------------------------------------------------------------

def test_deleting_a_timetable_entry_with_attendance_is_refused():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)

    save_sheet(
        headers, setup["entry_id"], date_for_weekday(setup["day"]), [{"student_id": setup["roster"][0]["id"], "status": "PRESENT"}]
    )

    response = client.delete(f"/api/timetable/{setup['entry_id']}", headers=headers)
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "1 attendance session" in detail
    # The message has to offer the way out.
    assert "pause" in detail.lower()


def test_deleting_a_student_with_attendance_is_refused():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    student = setup["roster"][0]

    save_sheet(
        headers, setup["entry_id"], date_for_weekday(setup["day"]), [{"student_id": student["id"], "status": "PRESENT"}]
    )

    response = client.delete(f"/api/students/{student['id']}", headers=headers)
    assert response.status_code == 409, response.text
    assert "INACTIVE" in response.json()["detail"]


def test_deleting_a_section_with_attendance_is_refused():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)

    save_sheet(
        headers, setup["entry_id"], date_for_weekday(setup["day"]), [{"student_id": setup["roster"][0]["id"], "status": "PRESENT"}]
    )

    response = client.delete(
        f"/api/sections/{setup['chain']['section_id']}", headers=headers
    )
    assert response.status_code == 409, response.text
    assert "attendance session" in response.json()["detail"]


def test_an_admin_can_delete_a_session_and_its_records_go_with_it():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    class_date = date_for_weekday(setup["day"])

    saved = save_sheet(
        headers,
        setup["entry_id"],
        class_date,
        [{"student_id": s["id"], "status": "PRESENT"} for s in setup["roster"]],
    ).json()
    session_id = saved["session"]["id"]

    assert client.delete(f"/api/attendance/sessions/{session_id}", headers=headers).status_code == 204

    # The register is gone, so the entry is deletable again.
    assert get_sheet(headers, setup["entry_id"], class_date).json()["session"] is None
    assert client.delete(f"/api/timetable/{setup['entry_id']}", headers=headers).status_code == 204
