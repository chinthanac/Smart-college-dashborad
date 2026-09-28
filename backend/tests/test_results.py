"""Results.

Every test here is guarding one of two things: that the weighted arithmetic is
right, and that the module refuses to invent a number it does not have. The
second is the harder discipline — a partial SGPA, a DRAFT mark counted early,
or an F standing in for "not computed" would all be believed by whoever reads
the screen.
"""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.test_assessments import (
    admin_headers,
    headers_for,
    make_assessment,
    make_assignment,
    make_faculty,
    make_student,
    make_subject,
    setup_class,
)

client = TestClient(app)


def save_marks(headers, assessment_id, pairs):
    """pairs: [(student_id, marks or None, extra_kwargs)] -> saved sheet."""
    entries = []
    for student_id, marks, *rest in pairs:
        entry = {"student_id": student_id, "marks_obtained": marks}
        if rest:
            entry.update(rest[0])
        entries.append(entry)
    response = client.post(
        "/api/marks/sheet",
        json={"assessment_id": assessment_id, "entries": entries},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def publish(headers, assessment_id):
    response = client.patch(
        f"/api/assessments/{assessment_id}/status", json={"action": "publish"}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def my_result(headers):
    response = client.get("/api/results/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def student_result(headers, student_id):
    response = client.get(
        "/api/results/student", params={"student_id": student_id}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def subject_report(headers, section_id, subject_id):
    response = client.get(
        "/api/results/subject",
        params={"section_id": section_id, "subject_id": subject_id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def section_report(headers, section_id):
    response = client.get(
        "/api/results/section", params={"section_id": section_id}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def subject_of(result, subject_id):
    return next(item for item in result["subjects"] if item["subject_id"] == subject_id)


def one_subject_graded(students=1, weights=((30, 50), (70, 100)), marks=None):
    """A class with two published components, fully marked.

    weights: ((weightage, max_marks), ...). marks: per student, per component.
    """
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=students)
    roster = setup["roster"]

    assessments = []
    for index, (weightage, max_marks) in enumerate(weights):
        assessment = make_assessment(
            headers,
            setup["assignment_id"],
            assessment_type="INTERNAL" if index == 0 else "EXTERNAL",
            name=f"Component {index + 1}",
            sequence_no=index + 1,
            max_marks=max_marks,
            weightage_percent=weightage,
        )
        assessments.append(assessment)

    for index, assessment in enumerate(assessments):
        pairs = [
            (student["id"], marks[student_index][index] if marks else 40.0)
            for student_index, student in enumerate(roster)
        ]
        save_marks(headers, assessment["id"], pairs)
        publish(headers, assessment["id"])

    setup["headers"] = headers
    setup["assessments"] = assessments
    return setup


# --------------------------------------------------------------------------
# the weighted arithmetic
# --------------------------------------------------------------------------

def test_weighted_percentage_across_components_of_unequal_weight():
    # Internal: 40/50 = 80% of 30 -> 24. External: 60/100 = 60% of 70 -> 42.
    # Total 66 of an allocated 100 -> 66.0%, which is a B+.
    setup = one_subject_graded(students=1, marks=[[40, 60]])
    result = student_result(setup["headers"], setup["roster"][0]["id"])

    subject = subject_of(result, setup["subject_id"])
    assert subject["allocated_weightage"] == 100.0
    assert subject["percent"] == 66.0
    assert subject["grade_letter"] == "B+"
    assert subject["grade_point"] == 7.0
    assert subject["is_pass"] is True
    assert subject["has_data"] is True
    assert subject["assessments_pending"] == 0

    breakdown = {item["name"]: item for item in subject["breakdown"]}
    assert breakdown["Component 1"]["weighted_contribution"] == 24.0
    assert breakdown["Component 2"]["weighted_contribution"] == 42.0
    assert breakdown["Component 1"]["percent"] == 80.0
    assert breakdown["Component 2"]["percent"] == 60.0


def test_partial_weightage_divides_by_what_has_actually_run():
    """A subject that has run one of two components reports an honest
    percentage of what happened, not a failure for the missing half."""
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    student_id = setup["roster"][0]["id"]

    run = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=30)
    # The other 70% exists but is still DRAFT, so it is not counted at all.
    make_assessment(
        headers,
        setup["assignment_id"],
        assessment_type="EXTERNAL",
        name="End Semester",
        max_marks=100,
        weightage_percent=70,
    )

    save_marks(headers, run["id"], [(student_id, 40)])
    publish(headers, run["id"])

    subject = subject_of(student_result(headers, student_id), setup["subject_id"])
    # 40/50 = 80% of an allocated 30 -> 80.0%, not 24.0%.
    assert subject["allocated_weightage"] == 30.0
    assert subject["percent"] == 80.0
    assert subject["grade_letter"] == "A+"
    assert subject["assessments_total"] == 1


def test_absent_contributes_zero_but_is_reported_as_absent():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    student_id = setup["roster"][0]["id"]

    first = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=50)
    second = make_assessment(
        headers,
        setup["assignment_id"],
        sequence_no=2,
        name="Internal 2",
        max_marks=50,
        weightage_percent=50,
    )

    save_marks(headers, first["id"], [(student_id, 45)])
    save_marks(headers, second["id"], [(student_id, None, {"is_absent": True})])
    publish(headers, first["id"])
    publish(headers, second["id"])

    subject = subject_of(student_result(headers, student_id), setup["subject_id"])
    # 45/50 = 90% of 50 -> 45. The absence contributes 0 of its 50.
    assert subject["percent"] == 45.0
    assert subject["grade_letter"] == "P"

    absent_row = next(
        item for item in subject["breakdown"] if item["name"] == "Internal 2"
    )
    assert absent_row["is_absent"] is True
    assert absent_row["marks_obtained"] is None
    assert absent_row["percent"] == 0.0
    assert absent_row["is_pending"] is False


def test_malpractice_contributes_zero_and_keeps_its_own_flag():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    student_id = setup["roster"][0]["id"]
    assessment = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=100)

    save_marks(headers, assessment["id"], [(student_id, None, {"is_malpractice": True})])
    publish(headers, assessment["id"])

    subject = subject_of(student_result(headers, student_id), setup["subject_id"])
    assert subject["percent"] == 0.0
    assert subject["grade_letter"] == "F"
    assert subject["is_pass"] is False
    assert subject["breakdown"][0]["is_malpractice"] is True


# --------------------------------------------------------------------------
# what the module refuses to compute
# --------------------------------------------------------------------------

def test_a_pending_mark_excludes_the_whole_subject():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=2)
    marked, skipped = setup["roster"]
    assessment = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=100)

    save_marks(headers, assessment["id"], [(marked["id"], 40)])
    publish(headers, assessment["id"])

    # The student who was marked is graded ...
    graded = subject_of(student_result(headers, marked["id"]), setup["subject_id"])
    assert graded["has_data"] is True
    assert graded["percent"] == 80.0

    # ... and the one who was skipped is NOT scored zero.
    missed = subject_of(student_result(headers, skipped["id"]), setup["subject_id"])
    assert missed["has_data"] is False
    assert missed["percent"] is None
    assert missed["grade_letter"] is None
    assert missed["grade_point"] is None
    assert missed["is_pass"] is None
    assert missed["assessments_pending"] == 1
    assert "no mark for this student yet" in missed["reason"]
    assert missed["breakdown"][0]["is_pending"] is True


def test_draft_assessments_reach_nobody():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    student_id = setup["roster"][0]["id"]
    assessment = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=100)
    save_marks(headers, assessment["id"], [(student_id, 45)])

    # Marked, but never published.
    result = student_result(headers, student_id)
    assert result["subjects"] == []
    assert result["has_data"] is False
    assert result["sgpa"] is None
    assert "No published assessments" in result["reason"]

    publish(headers, assessment["id"])
    after = student_result(headers, student_id)
    assert len(after["subjects"]) == 1
    assert after["has_data"] is True


def test_sgpa_is_withheld_while_any_subject_is_incomplete():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)
    student_id = setup["roster"][0]["id"]
    chain = setup["chain"]

    # A second subject on the same section, graded for nobody.
    other_subject = make_subject(headers, f"X{suffix}", chain, subject_code=f"SUBX{suffix}", credits=3)
    other_faculty = make_faculty(headers, f"X{suffix}", chain["department_id"])
    other_assignment = make_assignment(
        headers, other_faculty["id"], other_subject, chain["section_id"]
    )

    first = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=100)
    save_marks(headers, first["id"], [(student_id, 45)])
    publish(headers, first["id"])

    second = make_assessment(headers, other_assignment, max_marks=50, weightage_percent=100)
    # One mark so it can be published, but not for OUR student.
    extra = make_student(headers, f"Z{suffix}", chain)
    save_marks(headers, second["id"], [(extra["id"], 30)])
    publish(headers, second["id"])

    result = student_result(headers, student_id)
    assert result["subjects_complete"] == 1
    assert result["subjects_pending"] == 1
    assert result["sgpa"] is None, "a partial SGPA would be screenshotted and believed"
    assert result["overall_percent"] is None
    assert result["has_data"] is False
    assert f"SUBX{suffix}".upper() in result["reason"]


def test_sgpa_is_credit_weighted_once_every_subject_is_graded():
    headers = admin_headers()
    suffix = uuid.uuid4().hex[:6]
    setup = setup_class(headers, suffix, students=1)   # subject has 4 credits
    student_id = setup["roster"][0]["id"]
    chain = setup["chain"]

    other_subject = make_subject(
        headers, f"X{suffix}", chain, subject_code=f"SUBX{suffix}", credits=2
    )
    other_faculty = make_faculty(headers, f"X{suffix}", chain["department_id"])
    other_assignment = make_assignment(
        headers, other_faculty["id"], other_subject, chain["section_id"]
    )

    # 4-credit subject at 90% -> O -> 10 points.
    first = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=100)
    save_marks(headers, first["id"], [(student_id, 45)])
    publish(headers, first["id"])

    # 2-credit subject at 50% -> C -> 5 points.
    second = make_assessment(headers, other_assignment, max_marks=50, weightage_percent=100)
    save_marks(headers, second["id"], [(student_id, 25)])
    publish(headers, second["id"])

    result = student_result(headers, student_id)
    assert result["subjects_complete"] == 2
    assert result["subjects_pending"] == 0
    assert result["total_credits"] == 6
    assert result["earned_credits"] == 6
    # (10*4 + 5*2) / 6 = 8.33
    assert result["sgpa"] == 8.33
    # (90*4 + 50*2) / 6 = 76.67
    assert result["overall_percent"] == 76.67
    assert result["subjects_passed"] == 2
    assert result["subjects_failed"] == 0
    assert result["has_data"] is True


def test_a_failed_subject_still_produces_a_result():
    setup = one_subject_graded(students=1, weights=((100, 50),), marks=[[10]])
    result = student_result(setup["headers"], setup["roster"][0]["id"])

    subject = subject_of(result, setup["subject_id"])
    assert subject["percent"] == 20.0
    assert subject["grade_letter"] == "F"
    assert subject["grade_point"] == 0.0
    assert subject["is_pass"] is False

    assert result["has_data"] is True
    assert result["sgpa"] == 0.0
    assert result["subjects_failed"] == 1


# --------------------------------------------------------------------------
# grade bands
# --------------------------------------------------------------------------

def test_every_grade_boundary_lands_on_the_right_band():
    # One 100-mark component at 100% weightage: the mark IS the percentage.
    cases = [
        (100, "O", 10.0),
        (90, "O", 10.0),
        (89, "A+", 9.0),
        (80, "A+", 9.0),
        (79, "A", 8.0),
        (70, "A", 8.0),
        (60, "B+", 7.0),
        (55, "B", 6.0),
        (50, "C", 5.0),
        (40, "P", 4.0),
        (39, "F", 0.0),
        (0, "F", 0.0),
    ]
    setup = one_subject_graded(
        students=len(cases),
        weights=((100, 100),),
        marks=[[mark] for mark, _, _ in cases],
    )

    for index, (mark, letter, point) in enumerate(cases):
        result = student_result(setup["headers"], setup["roster"][index]["id"])
        subject = subject_of(result, setup["subject_id"])
        assert subject["percent"] == float(mark), f"mark {mark}"
        assert subject["grade_letter"] == letter, f"mark {mark}"
        assert subject["grade_point"] == point, f"mark {mark}"


def test_forty_is_a_pass_and_thirty_nine_is_not():
    setup = one_subject_graded(students=2, weights=((100, 100),), marks=[[40], [39]])
    headers = setup["headers"]

    passed = subject_of(student_result(headers, setup["roster"][0]["id"]), setup["subject_id"])
    failed = subject_of(student_result(headers, setup["roster"][1]["id"]), setup["subject_id"])

    assert passed["grade_letter"] == "P"
    assert passed["is_pass"] is True
    assert failed["grade_letter"] == "F"
    assert failed["is_pass"] is False


# --------------------------------------------------------------------------
# the subject report
# --------------------------------------------------------------------------

def test_subject_report_carries_distribution_pass_rate_and_topper():
    setup = one_subject_graded(
        students=4, weights=((100, 100),), marks=[[92], [71], [45], [30]]
    )
    report = subject_report(
        setup["headers"], setup["chain"]["section_id"], setup["subject_id"]
    )

    assert report["has_data"] is True
    assert report["total_students"] == 4
    assert report["graded_students"] == 4
    assert report["pending_students"] == 0
    assert report["pass_count"] == 3
    assert report["fail_count"] == 1
    assert report["pass_percentage"] == 75.0
    assert report["average_percent"] == 59.5
    assert report["highest_percent"] == 92.0
    assert report["lowest_percent"] == 30.0
    assert report["allocated_weightage"] == 100.0

    assert report["topper_student_id"] == setup["roster"][0]["id"]
    assert report["topper_student_name"] == "Arjun Menon"

    bands = {band["grade_letter"]: band["student_count"] for band in report["distribution"]}
    assert bands["O"] == 1      # 92
    assert bands["A"] == 1      # 71
    assert bands["P"] == 1      # 45
    assert bands["F"] == 1      # 30
    assert sum(bands.values()) == 4


def test_subject_report_says_why_it_is_empty_rather_than_showing_zeros():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=2)
    make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=100)

    report = subject_report(headers, setup["chain"]["section_id"], setup["subject_id"])
    assert report["has_data"] is False
    assert report["pass_percentage"] == 0.0
    assert report["average_percent"] is None
    assert report["distribution"] == []
    assert "No published assessments" in report["reason"]


# --------------------------------------------------------------------------
# the section mark sheet
# --------------------------------------------------------------------------

def test_section_report_builds_a_grid_of_students_against_subjects():
    setup = one_subject_graded(students=3, weights=((100, 100),), marks=[[88], [64], [35]])
    report = section_report(setup["headers"], setup["chain"]["section_id"])

    assert report["has_data"] is True
    assert report["total_students"] == 3
    assert report["complete_students"] == 3
    assert report["pending_students"] == 0
    assert len(report["subjects"]) == 1
    assert report["subjects"][0]["credits"] == 4

    rows = {row["student_id"]: row for row in report["students"]}
    top = rows[setup["roster"][0]["id"]]
    assert top["subject_percent"][str(setup["subject_id"])] == 88.0
    assert top["subject_grade"][str(setup["subject_id"])] == "A+"
    assert top["sgpa"] == 9.0
    assert top["has_data"] is True

    bottom = rows[setup["roster"][2]["id"]]
    assert bottom["subject_grade"][str(setup["subject_id"])] == "F"
    assert bottom["subjects_failed"] == 1

    assert report["pass_count"] == 2
    assert report["fail_count"] == 1
    assert report["pass_percentage"] == 66.67
    # (9.0 + 7.0 + 0.0) / 3
    assert report["average_sgpa"] == 5.33


def test_section_report_keeps_ungraded_students_as_nulls_in_the_grid():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=2)
    marked, skipped = setup["roster"]
    assessment = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=100)
    save_marks(headers, assessment["id"], [(marked["id"], 40)])
    publish(headers, assessment["id"])

    report = section_report(headers, setup["chain"]["section_id"])
    rows = {row["student_id"]: row for row in report["students"]}
    key = str(setup["subject_id"])

    assert rows[marked["id"]]["subject_percent"][key] == 80.0
    assert rows[skipped["id"]]["subject_percent"][key] is None
    assert rows[skipped["id"]]["subject_grade"][key] is None
    assert rows[skipped["id"]]["sgpa"] is None
    assert rows[skipped["id"]]["has_data"] is False
    assert rows[skipped["id"]]["subjects_pending"] == 1

    assert report["complete_students"] == 1
    assert report["pending_students"] == 1
    # The average is over the graded student only.
    assert report["average_sgpa"] == 9.0


# --------------------------------------------------------------------------
# attendance is reported, never enforced
# --------------------------------------------------------------------------

def test_attendance_is_absent_from_the_payload_when_nothing_is_recorded():
    setup = one_subject_graded(students=1, weights=((100, 100),), marks=[[75]])
    result = student_result(setup["headers"], setup["roster"][0]["id"])

    assert result["attendance_percent"] is None
    assert result["attendance_short"] is False
    assert result["attendance_threshold"] == 75.0
    # And the result is produced regardless.
    assert result["has_data"] is True
    assert result["sgpa"] == 8.0


# --------------------------------------------------------------------------
# who may read what
# --------------------------------------------------------------------------

def test_student_reads_their_own_result_and_only_published_marks():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    student = setup["roster"][0]
    student_headers = headers_for(student["email"], student["generated_password"])

    assessment = make_assessment(headers, setup["assignment_id"], max_marks=50, weightage_percent=100)
    save_marks(headers, assessment["id"], [(student["id"], 45)])

    # Still DRAFT — the student must see nothing.
    draft = my_result(student_headers)
    assert draft["subjects"] == []
    assert draft["has_data"] is False

    publish(headers, assessment["id"])
    published = my_result(student_headers)
    assert len(published["subjects"]) == 1
    assert published["subjects"][0]["percent"] == 90.0
    assert published["student_id"] == student["id"]


def test_staff_have_no_personal_result():
    headers = admin_headers()
    response = client.get("/api/results/me", headers=headers)
    assert response.status_code == 400, response.text
    assert "Only students" in response.json()["detail"]


def test_student_cannot_read_another_students_result():
    headers = admin_headers()
    setup = setup_class(headers, uuid.uuid4().hex[:6], students=2)
    first, second = setup["roster"]
    student_headers = headers_for(first["email"], first["generated_password"])

    response = client.get(
        "/api/results/student", params={"student_id": second["id"]}, headers=student_headers
    )
    assert response.status_code == 403, response.text

    section = client.get(
        "/api/results/section",
        params={"section_id": setup["chain"]["section_id"]},
        headers=student_headers,
    )
    assert section.status_code == 403, section.text


def test_faculty_are_scoped_to_their_own_department():
    headers = admin_headers()
    mine = setup_class(headers, uuid.uuid4().hex[:6], students=1)
    theirs = setup_class(headers, uuid.uuid4().hex[:6], students=1)

    teacher = headers_for(mine["faculty"]["email"], mine["faculty"]["generated_password"])

    own = client.get(
        "/api/results/section",
        params={"section_id": mine["chain"]["section_id"]},
        headers=teacher,
    )
    assert own.status_code == 200, own.text

    other = client.get(
        "/api/results/section",
        params={"section_id": theirs["chain"]["section_id"]},
        headers=teacher,
    )
    assert other.status_code == 403, other.text

    other_student = client.get(
        "/api/results/student",
        params={"student_id": theirs["roster"][0]["id"]},
        headers=teacher,
    )
    assert other_student.status_code == 403, other_student.text


def test_unknown_section_is_a_404():
    headers = admin_headers()
    response = client.get("/api/results/section", params={"section_id": 99999}, headers=headers)
    assert response.status_code == 404, response.text
