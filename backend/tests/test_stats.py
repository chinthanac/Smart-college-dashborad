"""Dashboard statistics.

These tests are mostly about honesty: that a count comes from a real row,
that a cancelled class counts toward nobody, and that "nothing marked yet" is
reported as such rather than as a confident 0%.
"""

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def admin_headers():
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@smartcollege.com", "password": "Chaadmin123@"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def headers_for(email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def date_for_weekday(day_of_week, weeks_back=0):
    today = date.today()
    delta = (today.weekday() - day_of_week) % 7
    return today - timedelta(days=delta + 7 * weeks_back)


def dashboard(headers):
    response = client.get("/api/stats/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


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
            "capacity": 4,
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


def make_student(headers, suffix, chain, **overrides):
    payload = {
        "student_id": f"ST{suffix}",
        "first_name": "Aarav",
        "last_name": "Sharma",
        "phone": "9876500000",
        "email": f"st.{suffix}@student.college.edu",
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


def setup_class(headers, suffix, students=2, day=0):
    chain = build_hierarchy(headers, suffix)

    subject = client.post(
        "/api/subjects",
        json={
            "course_id": chain["course_id"], "semester_id": chain["semester_id"],
            "subject_code": f"SB{suffix}", "name": "Electrical Machines",
            "credits": 4, "subject_type": "THEORY",
            "lecture_hours": 3, "tutorial_hours": 1, "practical_hours": 0,
            "is_active": True,
        },
        headers=headers,
    )
    assert subject.status_code == 201, subject.text

    faculty = client.post(
        "/api/faculty",
        json={
            "faculty_id": f"FST{suffix}", "department_id": chain["department_id"],
            "first_name": "Anand", "last_name": "Krishnan",
            "email": f"st.{suffix}@college.edu", "phone": "9876543210",
            "designation": "Professor", "qualification": "Ph.D",
            "joining_date": "2026-07-01", "employee_type": "Full Time",
            "is_active": True,
        },
        headers=headers,
    )
    assert faculty.status_code == 201, faculty.text

    assignment = client.post(
        "/api/teaching-assignments",
        json={
            "faculty_id": faculty.json()["id"], "subject_id": subject.json()["id"],
            "section_id": chain["section_id"], "notes": None, "is_active": True,
        },
        headers=headers,
    )
    assert assignment.status_code == 201, assignment.text

    slots = [
        s for s in client.get(
            "/api/time-slots", headers=headers, params={"is_active": True}
        ).json() if not s["is_break"]
    ]
    entry = client.post(
        "/api/timetable",
        json={
            "teaching_assignment_id": assignment.json()["id"], "day_of_week": day,
            "time_slot_id": slots[0]["id"], "room_number": None, "is_active": True,
        },
        headers=headers,
    )
    assert entry.status_code == 201, entry.text

    roster = [
        make_student(headers, f"{suffix}{i}", chain, student_id=f"ST{suffix}{i}")
        for i in range(students)
    ]
    return {
        "chain": chain,
        "assignment_id": assignment.json()["id"],
        "entry_id": entry.json()["id"],
        "roster": roster,
        "day": day,
    }


def save_sheet(headers, entry_id, class_date, records, **overrides):
    payload = {
        "timetable_entry_id": entry_id,
        "class_date": str(class_date),
        "session_status": "HELD",
        "records": records,
    }
    payload.update(overrides)
    response = client.post("/api/attendance/sheet", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# access
# --------------------------------------------------------------------------

def test_the_dashboard_is_admin_only():
    """It reports across every department, which is exactly what a
    department-scoped faculty account must not see."""
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)

    student = setup["roster"][0]
    student_headers = headers_for(student["email"], student["generated_password"])
    assert client.get("/api/stats/dashboard", headers=student_headers).status_code == 403
    assert client.get("/api/stats/dashboard").status_code == 403


# --------------------------------------------------------------------------
# counts
# --------------------------------------------------------------------------

def test_counts_move_when_a_row_is_added():
    headers = admin_headers()
    before = dashboard(headers)["counts"]

    suffix = uuid.uuid4().hex[:6]
    setup_class(headers, suffix, students=3)

    after = dashboard(headers)["counts"]
    assert after["departments"] == before["departments"] + 1
    assert after["courses"] == before["courses"] + 1
    assert after["sections"] == before["sections"] + 1
    assert after["subjects"] == before["subjects"] + 1
    assert after["faculty"] == before["faculty"] + 1
    assert after["students"] == before["students"] + 3
    assert after["teaching_assignments"] == before["teaching_assignments"] + 1
    assert after["timetable_entries"] == before["timetable_entries"] + 1


def test_active_students_excludes_the_ones_who_left():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    before = dashboard(headers)["counts"]

    client.patch(
        f"/api/students/{setup['roster'][0]['id']}/status",
        json={"status": "GRADUATED"},
        headers=headers,
    )

    after = dashboard(headers)["counts"]
    assert after["students"] == before["students"], "the student is not deleted"
    assert after["active_students"] == before["active_students"] - 1


def test_a_department_with_no_students_still_appears_at_zero():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    chain = build_hierarchy(headers, suffix)

    rows = dashboard(headers)["students_by_department"]
    mine = next(r for r in rows if r["department_id"] == chain["department_id"])
    assert mine["student_count"] == 0, "an empty department is shown, not hidden"


def test_students_by_department_counts_the_students_created_in_it():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=3)

    rows = dashboard(headers)["students_by_department"]
    mine = next(r for r in rows if r["department_id"] == setup["chain"]["department_id"])
    assert mine["student_count"] == 3


# --------------------------------------------------------------------------
# attendance
# --------------------------------------------------------------------------

def test_attendance_counts_late_as_present_and_drops_excused():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=3)
    before = dashboard(headers)["attendance"]
    present, late, excused = setup["roster"]

    save_sheet(
        headers, setup["entry_id"], date_for_weekday(setup["day"]),
        [
            {"student_id": present["id"], "status": "PRESENT"},
            {"student_id": late["id"], "status": "LATE"},
            {"student_id": excused["id"], "status": "EXCUSED"},
        ],
    )

    after = dashboard(headers)["attendance"]
    assert after["held_sessions"] == before["held_sessions"] + 1
    assert after["present_count"] == before["present_count"] + 2   # PRESENT + LATE
    assert after["excused_count"] == before["excused_count"] + 1
    assert after["countable_count"] == before["countable_count"] + 2
    assert after["has_data"] is True


def test_a_cancelled_class_counts_toward_nobody():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    before = dashboard(headers)["attendance"]

    save_sheet(
        headers, setup["entry_id"], date_for_weekday(setup["day"]), [],
        session_status="CANCELLED", cancel_reason="Public holiday",
    )

    after = dashboard(headers)["attendance"]
    assert after["cancelled_sessions"] == before["cancelled_sessions"] + 1
    assert after["held_sessions"] == before["held_sessions"]
    assert after["countable_count"] == before["countable_count"]


def test_the_series_anchors_on_the_newest_data_not_on_today():
    """A college whose term ended last year must show the months it taught,
    not twelve empty buckets ending this month."""
    headers = admin_headers()
    series = dashboard(headers)["attendance_series"]

    assert len(series["months"]) == 12
    assert series["anchor_month"] is not None
    # The window ends on the anchor.
    assert series["months"][-1]["month"] == series["anchor_month"]
    # And runs forward in time.
    assert [m["month"] for m in series["months"]] == sorted(m["month"] for m in series["months"])


def test_a_month_with_no_classes_is_a_bucket_not_a_gap():
    headers = admin_headers()
    series = dashboard(headers)["attendance_series"]

    for point in series["months"]:
        assert "has_data" in point
        if not point["has_data"]:
            assert point["held_sessions"] == 0
            # A month with nothing taught reports 0 sessions, and the UI reads
            # has_data to know that is "no classes", not "nobody came".
            assert point["attendance_percentage"] == 0.0


# --------------------------------------------------------------------------
# today, capacity, registers
# --------------------------------------------------------------------------

def test_today_counts_the_classes_that_meet_today():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    before = dashboard(headers)["today"]
    setup = setup_class(headers, suffix, students=2, day=date.today().weekday())

    after = dashboard(headers)["today"]
    assert after["day_of_week"] == date.today().weekday()
    assert after["scheduled_classes"] == before["scheduled_classes"] + 1
    assert after["unmarked_classes"] == before["unmarked_classes"] + 1

    save_sheet(
        headers, setup["entry_id"], date.today(),
        [{"student_id": s["id"], "status": "PRESENT"} for s in setup["roster"]],
    )

    marked = dashboard(headers)["today"]
    assert marked["marked_sessions"] == after["marked_sessions"] + 1
    assert marked["unmarked_classes"] == after["unmarked_classes"] - 1


def test_unmarked_classes_never_goes_negative():
    headers = admin_headers()
    today = dashboard(headers)["today"]
    assert today["unmarked_classes"] >= 0


def test_section_fill_reports_enrolment_against_capacity():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)   # capacity is 4

    rows = dashboard(headers)["section_fill"]
    mine = [r for r in rows if r["section_id"] == setup["chain"]["section_id"]]
    if mine:   # the panel is capped, so a small section may not make the cut
        assert mine[0]["enrolled"] == 2
        assert mine[0]["capacity"] == 4
        assert mine[0]["fill_percentage"] == 50.0
        assert mine[0]["over_capacity"] is False


def test_recent_registers_report_the_class_date():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=2)
    class_date = date_for_weekday(setup["day"])

    save_sheet(
        headers, setup["entry_id"], class_date,
        [{"student_id": s["id"], "status": "PRESENT"} for s in setup["roster"]],
    )

    rows = dashboard(headers)["recent_registers"]
    assert rows, "a register was just saved"
    # class_date, never marked_at — the latter is tz-aware over naive storage.
    assert all("class_date" in row for row in rows)
    assert all("marked_at" not in row for row in rows)


def test_unscheduled_assignments_counts_teaching_with_no_timetable_entry():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    before = dashboard(headers)["unscheduled_assignments"]

    # A second subject for the same section, assigned but never scheduled.
    subject = client.post(
        "/api/subjects",
        json={
            "course_id": setup["chain"]["course_id"],
            "semester_id": setup["chain"]["semester_id"],
            "subject_code": f"SBX{suffix}", "name": "Power Systems",
            "credits": 3, "subject_type": "THEORY",
            "lecture_hours": 3, "tutorial_hours": 0, "practical_hours": 0,
            "is_active": True,
        },
        headers=headers,
    )
    faculty_id = client.get(
        "/api/teaching-assignments", headers=headers,
        params={"section_id": setup["chain"]["section_id"]},
    ).json()[0]["faculty_id"]

    client.post(
        "/api/teaching-assignments",
        json={
            "faculty_id": faculty_id, "subject_id": subject.json()["id"],
            "section_id": setup["chain"]["section_id"], "notes": None, "is_active": True,
        },
        headers=headers,
    )

    assert dashboard(headers)["unscheduled_assignments"] == before + 1


# --------------------------------------------------------------------------
# shape
# --------------------------------------------------------------------------

def test_the_payload_carries_nothing_it_cannot_know():
    """Events, trend deltas and forecasts have no model behind them, so the
    endpoint must not invent fields for them.

    Marks and grades USED to be on this list. The assessments module now
    exists, so they are real — but CGPA still is not (nothing stores a prior
    semester), and neither does anything here store a previous period to
    compare against.
    """
    body = dashboard(admin_headers())
    flat = repr(body).lower()

    for forbidden in ("cgpa", "event", "delta", "forecast", "predict", "vs_last"):
        assert forbidden not in flat, f"{forbidden} has no data behind it"


# --------------------------------------------------------------------------
# assessments on the dashboard
#
# The rule this section guards: the dashboard may not state anything the
# results module would not. A draft reaches nobody, and an incomplete sheet
# produces no grade rather than a zero.
# --------------------------------------------------------------------------

def _assessment_setup(students=2):
    from tests.test_assessments import admin_headers, make_assessment, setup_class

    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=students)
    setup["headers"] = headers
    setup["make_assessment"] = make_assessment
    return setup


def _dashboard(headers):
    response = client.get("/api/stats/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["assessments"]


def test_dashboard_counts_drafts_separately_and_excludes_them_from_grades():
    setup = _assessment_setup(students=2)
    headers = setup["headers"]
    assessment = setup["make_assessment"](
        headers, setup["assignment_id"], max_marks=50, weightage_percent=100
    )

    client.post(
        "/api/marks/sheet",
        json={
            "assessment_id": assessment["id"],
            "entries": [
                {"student_id": student["id"], "marks_obtained": 40}
                for student in setup["roster"]
            ],
        },
        headers=headers,
    )

    before = _dashboard(headers)
    assert before["draft_assessments"] >= 1
    # Marks exist, but nothing is published — so no grade may be claimed.
    draft_only_graded = before["graded_results"]

    client.patch(
        f"/api/assessments/{assessment['id']}/status",
        json={"action": "publish"},
        headers=headers,
    )

    after = _dashboard(headers)
    assert after["published_assessments"] >= 1
    assert after["graded_results"] == draft_only_graded + 2
    assert after["has_data"] is True


def test_dashboard_reports_incomplete_sheets_rather_than_scoring_them():
    setup = _assessment_setup(students=3)
    headers = setup["headers"]
    assessment = setup["make_assessment"](
        headers, setup["assignment_id"], max_marks=50, weightage_percent=100
    )

    # Two of three marked, then published.
    client.post(
        "/api/marks/sheet",
        json={
            "assessment_id": assessment["id"],
            "entries": [
                {"student_id": setup["roster"][0]["id"], "marks_obtained": 45},
                # 15 of 50 is 30% — a genuine F. 20 would be exactly 40%,
                # which is the P boundary and therefore a pass.
                {"student_id": setup["roster"][1]["id"], "marks_obtained": 15},
            ],
        },
        headers=headers,
    )
    client.patch(
        f"/api/assessments/{assessment['id']}/status",
        json={"action": "publish"},
        headers=headers,
    )

    stats = _dashboard(headers)
    assert stats["incomplete_sheets"] >= 1

    row = next(
        item for item in stats["weakest_subjects"]
        if item["section_id"] == setup["chain"]["section_id"]
    )
    # The unmarked student is absent from the grades entirely — not a zero,
    # and not a failure.
    assert row["graded_students"] == 2
    assert row["pass_count"] == 1
    assert row["fail_count"] == 1
    assert row["pass_percentage"] == 50.0


def test_dashboard_distribution_matches_the_marks_that_were_entered():
    setup = _assessment_setup(students=2)
    headers = setup["headers"]
    assessment = setup["make_assessment"](
        headers, setup["assignment_id"], max_marks=100, weightage_percent=100
    )

    client.post(
        "/api/marks/sheet",
        json={
            "assessment_id": assessment["id"],
            "entries": [
                {"student_id": setup["roster"][0]["id"], "marks_obtained": 95},
                {"student_id": setup["roster"][1]["id"], "marks_obtained": 30},
            ],
        },
        headers=headers,
    )
    client.patch(
        f"/api/assessments/{assessment['id']}/status",
        json={"action": "publish"},
        headers=headers,
    )

    stats = _dashboard(headers)
    bands = {band["grade_letter"]: band for band in stats["distribution"]}

    # Every band is present so the chart has a stable shape, and the two
    # marks land in O and F.
    assert set(bands) == {"O", "A+", "A", "B+", "B", "C", "P", "F"}
    assert bands["O"]["student_count"] >= 1
    assert bands["F"]["student_count"] >= 1
    assert sum(band["student_count"] for band in stats["distribution"]) == stats["graded_results"]
