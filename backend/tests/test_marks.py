"""Marks entry.

The invariant almost every test here is protecting: **a missing mark is not a
zero**. "Not entered" is the absence of a row, and it has to survive a save, a
partial save, a clear and a read without ever turning into a 0 that somebody
later mistakes for a real one.

The rest is bounds, the absent/malpractice rules, and the scoping that keeps
one lecturer out of another's sheet.
"""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.test_assessments import (  # the hierarchy builders are identical
    admin_headers,
    headers_for,
    make_assessment,
    setup_class,
)

client = TestClient(app)


def sheet_for(headers, assessment_id):
    response = client.get(
        "/api/marks/sheet", params={"assessment_id": assessment_id}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def save(headers, assessment_id, entries):
    return client.post(
        "/api/marks/sheet",
        json={"assessment_id": assessment_id, "entries": entries},
        headers=headers,
    )


def rows_by_student(sheet):
    return {row["student_id"]: row for row in sheet["records"]}


def setup_sheet(students=3, **assessment_overrides):
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=students)
    assessment = make_assessment(headers, setup["assignment_id"], **assessment_overrides)
    setup["assessment"] = assessment
    setup["headers"] = headers
    return setup


# --------------------------------------------------------------------------
# the roster, and what a pending row looks like
# --------------------------------------------------------------------------

def test_fresh_sheet_carries_the_active_roster_as_pending_rows():
    setup = setup_sheet(students=3, max_marks=50)
    sheet = sheet_for(setup["headers"], setup["assessment"]["id"])

    assert sheet["total_students"] == 3
    assert sheet["entered_count"] == 0
    assert sheet["pending_count"] == 3
    assert sheet["sheet_state"] == "EMPTY"
    assert sheet["editable"] is True
    assert sheet["locked_reason"] is None
    assert sheet["max_marks"] == 50.0
    assert sheet["pass_marks"] == 20.0
    assert sheet["subject_name"] == "Database Management Systems"
    assert sheet["section_name"] == "Section A"

    for row in sheet["records"]:
        # Nothing may stand in for "we do not know".
        assert row["marks_obtained"] is None
        assert row["percent"] is None
        assert row["grade_letter"] is None
        assert row["is_pass"] is None
        assert row["row_state"] == "PENDING"
        assert row["id"] is None
        assert row["student_name"]
        assert row["student_code"]


def test_sheet_is_read_only_and_creates_nothing():
    setup = setup_sheet(students=2)
    sheet_for(setup["headers"], setup["assessment"]["id"])
    sheet_for(setup["headers"], setup["assessment"]["id"])

    after = client.get(
        f"/api/assessments/{setup['assessment']['id']}", headers=setup["headers"]
    ).json()
    assert after["entered_count"] == 0
    assert after["pending_count"] == 2


# --------------------------------------------------------------------------
# saving
# --------------------------------------------------------------------------

def test_saving_marks_computes_percent_grade_and_totals():
    setup = setup_sheet(students=2, max_marks=50)
    roster = setup["roster"]

    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [
            {"student_id": roster[0]["id"], "marks_obtained": 45},
            {"student_id": roster[1]["id"], "marks_obtained": 10},
        ],
    )
    assert response.status_code == 200, response.text
    sheet = response.json()
    rows = rows_by_student(sheet)

    top = rows[roster[0]["id"]]
    assert top["marks_obtained"] == 45.0
    assert top["percent"] == 90.0
    assert top["grade_letter"] == "O"
    assert top["is_pass"] is True
    assert top["row_state"] == "ENTERED"
    assert top["entered_by_name"] == "System Administrator"

    bottom = rows[roster[1]["id"]]
    assert bottom["percent"] == 20.0
    assert bottom["grade_letter"] == "F"
    assert bottom["is_pass"] is False

    assert sheet["sheet_state"] == "COMPLETE"
    assert sheet["entered_count"] == 2
    assert sheet["pending_count"] == 0
    assert sheet["average_marks"] == 27.5
    assert sheet["average_percent"] == 55.0
    assert sheet["highest_marks"] == 45.0
    assert sheet["lowest_marks"] == 10.0
    assert sheet["pass_count"] == 1
    assert sheet["fail_count"] == 1


def test_partial_save_leaves_the_rest_pending_not_zero():
    setup = setup_sheet(students=3, max_marks=50)
    roster = setup["roster"]

    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [{"student_id": roster[0]["id"], "marks_obtained": 30}],
    )
    assert response.status_code == 200, response.text
    sheet = response.json()

    assert sheet["sheet_state"] == "PARTIAL"
    assert sheet["entered_count"] == 1
    assert sheet["pending_count"] == 2

    rows = rows_by_student(sheet)
    for student in roster[1:]:
        row = rows[student["id"]]
        assert row["marks_obtained"] is None, "an untouched student must not become a zero"
        assert row["row_state"] == "PENDING"
        assert row["is_pass"] is None

    # The average is over entered marks only — the two pending students must
    # not drag it down as if they had scored nothing.
    assert sheet["average_marks"] == 30.0


def test_saving_twice_corrects_rather_than_duplicating():
    setup = setup_sheet(students=1, max_marks=50)
    student_id = setup["roster"][0]["id"]

    save(setup["headers"], setup["assessment"]["id"], [{"student_id": student_id, "marks_obtained": 20}])
    second = save(
        setup["headers"],
        setup["assessment"]["id"],
        [{"student_id": student_id, "marks_obtained": 44, "remarks": "Re-totalled"}],
    )
    assert second.status_code == 200, second.text
    sheet = second.json()

    assert len(sheet["records"]) == 1
    assert sheet["entered_count"] == 1
    row = sheet["records"][0]
    assert row["marks_obtained"] == 44.0
    assert row["remarks"] == "Re-totalled"


def test_clearing_a_mark_returns_the_student_to_pending():
    setup = setup_sheet(students=2, max_marks=50)
    roster = setup["roster"]

    save(
        setup["headers"],
        setup["assessment"]["id"],
        [
            {"student_id": roster[0]["id"], "marks_obtained": 40},
            {"student_id": roster[1]["id"], "marks_obtained": 25},
        ],
    )

    cleared = save(
        setup["headers"],
        setup["assessment"]["id"],
        [{"student_id": roster[0]["id"], "marks_obtained": None}],
    )
    assert cleared.status_code == 200, cleared.text
    sheet = cleared.json()
    rows = rows_by_student(sheet)

    # Cleared means pending, not zero.
    assert rows[roster[0]["id"]]["marks_obtained"] is None
    assert rows[roster[0]["id"]]["row_state"] == "PENDING"
    assert rows[roster[1]["id"]]["marks_obtained"] == 25.0

    assert sheet["entered_count"] == 1
    assert sheet["pending_count"] == 1
    assert sheet["sheet_state"] == "PARTIAL"


def test_zero_is_a_real_mark_and_survives():
    setup = setup_sheet(students=1, max_marks=50)
    student_id = setup["roster"][0]["id"]

    response = save(
        setup["headers"], setup["assessment"]["id"], [{"student_id": student_id, "marks_obtained": 0}]
    )
    assert response.status_code == 200, response.text
    row = response.json()["records"][0]

    assert row["marks_obtained"] == 0.0
    assert row["row_state"] == "ENTERED"
    assert row["percent"] == 0.0
    assert row["grade_letter"] == "F"
    assert row["is_pass"] is False
    assert response.json()["entered_count"] == 1
    assert response.json()["pending_count"] == 0


# --------------------------------------------------------------------------
# bounds
# --------------------------------------------------------------------------

def test_mark_above_the_maximum_is_rejected_by_student_name():
    setup = setup_sheet(students=1, max_marks=50)
    student_id = setup["roster"][0]["id"]

    response = save(
        setup["headers"], setup["assessment"]["id"], [{"student_id": student_id, "marks_obtained": 55}]
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "Arjun Menon" in detail
    assert "55.0" in detail
    assert "50.0" in detail


def test_negative_mark_is_rejected_at_the_payload_edge():
    setup = setup_sheet(students=1, max_marks=50)
    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [{"student_id": setup["roster"][0]["id"], "marks_obtained": -1}],
    )
    assert response.status_code == 422, response.text


def test_a_rejected_cell_leaves_the_whole_sheet_unwritten():
    setup = setup_sheet(students=3, max_marks=50)
    roster = setup["roster"]

    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [
            {"student_id": roster[0]["id"], "marks_obtained": 40},
            {"student_id": roster[1]["id"], "marks_obtained": 35},
            {"student_id": roster[2]["id"], "marks_obtained": 99},  # over the maximum
        ],
    )
    assert response.status_code == 400, response.text

    # All-or-nothing: the two valid marks above must NOT have landed.
    sheet = sheet_for(setup["headers"], setup["assessment"]["id"])
    assert sheet["entered_count"] == 0
    assert sheet["pending_count"] == 3


def test_student_from_another_section_is_refused():
    setup = setup_sheet(students=1)
    outsider = setup_sheet(students=1)

    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [{"student_id": outsider["roster"][0]["id"], "marks_obtained": 10}],
    )
    assert response.status_code == 400, response.text
    assert "is not in" in response.json()["detail"]


def test_duplicate_student_on_one_sheet_is_refused():
    setup = setup_sheet(students=1, max_marks=50)
    student_id = setup["roster"][0]["id"]

    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [
            {"student_id": student_id, "marks_obtained": 30},
            {"student_id": student_id, "marks_obtained": 40},
        ],
    )
    assert response.status_code == 400, response.text
    assert "appears twice" in response.json()["detail"]


# --------------------------------------------------------------------------
# absent and malpractice
# --------------------------------------------------------------------------

def test_absent_carries_no_mark_and_counts_separately():
    setup = setup_sheet(students=2, max_marks=50)
    roster = setup["roster"]

    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [
            {"student_id": roster[0]["id"], "marks_obtained": 40},
            {"student_id": roster[1]["id"], "is_absent": True, "remarks": "Medical"},
        ],
    )
    assert response.status_code == 200, response.text
    sheet = response.json()
    rows = rows_by_student(sheet)

    absent = rows[roster[1]["id"]]
    assert absent["marks_obtained"] is None
    assert absent["is_absent"] is True
    assert absent["row_state"] == "ABSENT"
    assert absent["is_pass"] is False
    assert absent["remarks"] == "Medical"

    # Accounted for, so not pending — but counted as its own fact, and kept
    # out of the average.
    assert sheet["entered_count"] == 2
    assert sheet["pending_count"] == 0
    assert sheet["absent_count"] == 1
    assert sheet["sheet_state"] == "COMPLETE"
    assert sheet["average_marks"] == 40.0
    assert sheet["pass_count"] == 1
    assert sheet["fail_count"] == 1


def test_absent_with_a_mark_is_refused():
    setup = setup_sheet(students=1, max_marks=50)
    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [{"student_id": setup["roster"][0]["id"], "marks_obtained": 30, "is_absent": True}],
    )
    assert response.status_code == 400, response.text
    assert "no mark can be recorded" in response.json()["detail"]


def test_malpractice_is_its_own_state():
    setup = setup_sheet(students=1, max_marks=50)
    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [{"student_id": setup["roster"][0]["id"], "is_malpractice": True}],
    )
    assert response.status_code == 200, response.text
    sheet = response.json()
    row = sheet["records"][0]

    assert row["row_state"] == "MALPRACTICE"
    assert row["marks_obtained"] is None
    assert row["is_pass"] is False
    assert sheet["malpractice_count"] == 1
    assert sheet["absent_count"] == 0


def test_absent_and_malpractice_together_are_refused():
    setup = setup_sheet(students=1)
    response = save(
        setup["headers"],
        setup["assessment"]["id"],
        [{"student_id": setup["roster"][0]["id"], "is_absent": True, "is_malpractice": True}],
    )
    assert response.status_code == 400, response.text
    assert "at once" in response.json()["detail"]


# --------------------------------------------------------------------------
# who may enter what
# --------------------------------------------------------------------------

def test_faculty_may_enter_on_their_own_class_only():
    mine = setup_sheet(students=1, max_marks=50)
    theirs = setup_sheet(students=1, max_marks=50)

    teacher = headers_for(
        mine["faculty"]["email"], mine["faculty"]["generated_password"]
    )

    own = save(
        teacher, mine["assessment"]["id"], [{"student_id": mine["roster"][0]["id"], "marks_obtained": 33}]
    )
    assert own.status_code == 200, own.text
    assert own.json()["records"][0]["entered_by_name"] == "Meera Iyer"

    other = save(
        teacher,
        theirs["assessment"]["id"],
        [{"student_id": theirs["roster"][0]["id"], "marks_obtained": 33}],
    )
    assert other.status_code == 403, other.text
    assert "classes you teach" in other.json()["detail"]


def test_locked_sheet_refuses_faculty_entry_but_admits_admin_correction():
    setup = setup_sheet(students=1, max_marks=50)
    headers = setup["headers"]
    student_id = setup["roster"][0]["id"]
    teacher = headers_for(
        setup["faculty"]["email"], setup["faculty"]["generated_password"]
    )

    save(headers, setup["assessment"]["id"], [{"student_id": student_id, "marks_obtained": 30}])
    client.patch(
        f"/api/assessments/{setup['assessment']['id']}/status",
        json={"action": "publish"},
        headers=headers,
    )
    client.patch(
        f"/api/assessments/{setup['assessment']['id']}/status",
        json={"action": "lock"},
        headers=headers,
    )

    # The sheet still opens for the lecturer, but it opens read-only and says
    # why, so the screen and the API agree about the fields.
    sheet = sheet_for(teacher, setup["assessment"]["id"])
    assert sheet["editable"] is False
    assert "locked" in sheet["locked_reason"]

    blocked = save(teacher, setup["assessment"]["id"], [{"student_id": student_id, "marks_obtained": 45}])
    assert blocked.status_code == 403, blocked.text

    corrected = save(headers, setup["assessment"]["id"], [{"student_id": student_id, "marks_obtained": 45}])
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["records"][0]["marks_obtained"] == 45.0


def test_inactive_assessment_refuses_entry_for_everyone():
    setup = setup_sheet(students=1, max_marks=50)
    headers = setup["headers"]
    client.patch(
        f"/api/assessments/{setup['assessment']['id']}", json={"is_active": False}, headers=headers
    )

    response = save(
        headers, setup["assessment"]["id"], [{"student_id": setup["roster"][0]["id"], "marks_obtained": 10}]
    )
    assert response.status_code == 400, response.text
    assert "inactive" in response.json()["detail"]

    sheet = sheet_for(headers, setup["assessment"]["id"])
    assert sheet["editable"] is False


def test_students_cannot_reach_the_marks_endpoints():
    setup = setup_sheet(students=1)
    student = setup["roster"][0]
    student_headers = headers_for(student["email"], student["generated_password"])

    read = client.get(
        "/api/marks/sheet", params={"assessment_id": setup["assessment"]["id"]}, headers=student_headers
    )
    assert read.status_code == 403, read.text

    write = save(
        student_headers, setup["assessment"]["id"], [{"student_id": student["id"], "marks_obtained": 50}]
    )
    assert write.status_code == 403, write.text


def test_faculty_from_another_department_cannot_read_the_sheet():
    mine = setup_sheet(students=1)
    theirs = setup_sheet(students=1)

    teacher = headers_for(mine["faculty"]["email"], mine["faculty"]["generated_password"])
    response = client.get(
        "/api/marks/sheet",
        params={"assessment_id": theirs["assessment"]["id"]},
        headers=teacher,
    )
    assert response.status_code == 403, response.text


# --------------------------------------------------------------------------
# a student who leaves the roster keeps the marks they earned
# --------------------------------------------------------------------------

def test_suspended_student_keeps_their_saved_marks():
    setup = setup_sheet(students=2, max_marks=50)
    headers = setup["headers"]
    roster = setup["roster"]

    save(
        headers,
        setup["assessment"]["id"],
        [
            {"student_id": roster[0]["id"], "marks_obtained": 48},
            {"student_id": roster[1]["id"], "marks_obtained": 22},
        ],
    )

    suspended = client.patch(
        f"/api/students/{roster[0]['id']}/status", json={"status": "SUSPENDED"}, headers=headers
    )
    assert suspended.status_code == 200, suspended.text

    sheet = sheet_for(headers, setup["assessment"]["id"])
    rows = rows_by_student(sheet)

    # Off the ACTIVE roster, but their mark is still on the sheet.
    assert sheet["total_students"] == 1
    assert rows[roster[0]["id"]]["marks_obtained"] == 48.0
    assert rows[roster[0]["id"]]["student_status"] == "SUSPENDED"

    # And it can still be corrected.
    corrected = save(
        headers, setup["assessment"]["id"], [{"student_id": roster[0]["id"], "marks_obtained": 49}]
    )
    assert corrected.status_code == 200, corrected.text


def test_student_with_marks_cannot_be_deleted():
    setup = setup_sheet(students=1, max_marks=50)
    student_id = setup["roster"][0]["id"]
    save(setup["headers"], setup["assessment"]["id"], [{"student_id": student_id, "marks_obtained": 30}])

    response = client.delete(f"/api/students/{student_id}", headers=setup["headers"])
    assert response.status_code == 409, response.text
    assert "mark record(s)" in response.json()["detail"]


# --------------------------------------------------------------------------
# "what do I still have to enter"
# --------------------------------------------------------------------------

def test_my_assessments_reports_progress_and_sorts_pending_first():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=4)
    teacher = headers_for(setup["faculty"]["email"], setup["faculty"]["generated_password"])

    first = make_assessment(headers, setup["assignment_id"], name="Internal 1", max_marks=50)
    second = make_assessment(
        headers,
        setup["assignment_id"],
        assessment_type="ASSIGNMENT",
        name="Assignment 1",
        max_marks=20,
        weightage_percent=20,
    )

    # Finish one sheet, leave the other half done.
    save(
        teacher,
        second["id"],
        [{"student_id": student["id"], "marks_obtained": 15} for student in setup["roster"]],
    )
    save(
        teacher,
        first["id"],
        [{"student_id": student["id"], "marks_obtained": 30} for student in setup["roster"][:2]],
    )

    response = client.get("/api/marks/my-assessments", headers=teacher)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2

    # Outstanding work first — that is what the screen is for.
    assert rows[0]["name"] == "Internal 1"
    assert rows[0]["state"] == "PENDING"
    assert rows[0]["total_students"] == 4
    assert rows[0]["entered_count"] == 2
    assert rows[0]["pending_count"] == 2
    assert rows[0]["completion_percent"] == 50.0
    assert rows[0]["subject_code"]
    assert rows[0]["section_name"] == "Section A"

    assert rows[1]["name"] == "Assignment 1"
    assert rows[1]["state"] == "COMPLETE"
    assert rows[1]["pending_count"] == 0
    assert rows[1]["completion_percent"] == 100.0

    only_pending = client.get(
        "/api/marks/my-assessments", params={"only_pending": True}, headers=teacher
    ).json()
    assert [row["name"] for row in only_pending] == ["Internal 1"]


def test_my_assessments_never_shows_another_lecturers_work():
    mine = setup_sheet(students=1)
    theirs = setup_sheet(students=1)

    teacher = headers_for(mine["faculty"]["email"], mine["faculty"]["generated_password"])
    rows = client.get("/api/marks/my-assessments", headers=teacher).json()

    ids = {row["assessment_id"] for row in rows}
    assert mine["assessment"]["id"] in ids
    assert theirs["assessment"]["id"] not in ids


def test_locked_assessment_reports_as_locked_not_pending():
    setup = setup_sheet(students=1, max_marks=50)
    headers = setup["headers"]
    teacher = headers_for(setup["faculty"]["email"], setup["faculty"]["generated_password"])

    save(headers, setup["assessment"]["id"], [{"student_id": setup["roster"][0]["id"], "marks_obtained": 30}])
    client.patch(
        f"/api/assessments/{setup['assessment']['id']}/status", json={"action": "publish"}, headers=headers
    )
    client.patch(
        f"/api/assessments/{setup['assessment']['id']}/status", json={"action": "lock"}, headers=headers
    )

    rows = client.get("/api/marks/my-assessments", headers=teacher).json()
    row = next(item for item in rows if item["assessment_id"] == setup["assessment"]["id"])
    assert row["state"] == "LOCKED"
    assert row["editable"] is False


# --------------------------------------------------------------------------
# the progress the assessment row reports agrees with the sheet
# --------------------------------------------------------------------------

def test_assessment_row_progress_matches_the_sheet():
    setup = setup_sheet(students=3, max_marks=50)
    roster = setup["roster"]

    save(
        setup["headers"],
        setup["assessment"]["id"],
        [
            {"student_id": roster[0]["id"], "marks_obtained": 45},
            {"student_id": roster[1]["id"], "is_absent": True},
        ],
    )

    sheet = sheet_for(setup["headers"], setup["assessment"]["id"])
    row = client.get(
        f"/api/assessments/{setup['assessment']['id']}", headers=setup["headers"]
    ).json()

    assert row["total_students"] == sheet["total_students"] == 3
    assert row["entered_count"] == sheet["entered_count"] == 2
    assert row["pending_count"] == sheet["pending_count"] == 1
    assert row["absent_count"] == sheet["absent_count"] == 1
    assert row["average_marks"] == sheet["average_marks"] == 45.0
    assert row["is_complete"] is False
