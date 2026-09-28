# Module Spec — Examinations, Internal Marks & Results

Status: **implemented** — all six steps of section 9 are done and covered by
tests. Backend suite: **217 passing, 0 failing**. Frontend builds clean.
Depends on: teaching assignments, subjects, sections, students, attendance
Supersedes: nothing. This is the next module after attendance.

---

## 1. Why this module, and why now

Nine modules exist and layer cleanly:

```
department -> course -> academic year -> semester -> section
                                            |
                          faculty ----------+---------- students
                                            |
                                        subjects
                                            |
                                  teaching assignments      (who teaches what, to whom)
                                            |
                                    timetable entries       (when it meets)
                                            |
                                  attendance sessions       (it actually happened)
```

Every layer anchors on the one below it and copies its identity from that anchor
rather than accepting it from the client. Assessments continue the chain from
teaching assignments: *who teaches what to whom* is already settled, so a
gradable component attaches to that fact and cannot contradict it.

The gap is named twice in the code already:

- `app/schemas/stats.py` forbids marks/GPA fields on the dashboard because
  "there is no marks module, so every such field would be fabrication";
- `app/models/subject.py` records that attendance and marks "will later be
  calculated differently per type".

`Subject.credits` is already populated, so weighted aggregation has its input.

---

## 2. Shape

Three concepts, one of which is deliberately not a table.

| concept | storage | anchor |
| --- | --- | --- |
| **Assessment** | `assessments` | `teaching_assignment_id` |
| **MarkRecord** | `mark_records` | `assessment_id` + `student_id` |
| **Result** | *computed at read time* | published marks + `subject.credits` |

### Why Result is not a table

A stored grade is a second source of truth. The moment a mark is corrected —
and marks are corrected constantly — the stored row is wrong until something
recomputes it, and nothing guarantees that something runs. Derivation is cheap
here (one section is a few hundred rows) and it is always right.

A frozen `SemesterResult` snapshot is a *later* phase, taken once at
end-of-semester sign-off, explicitly labelled as a snapshot with the timestamp
it was taken. It does not belong in this module.

---

## 3. Models

### 3.1 `Assessment` (`app/models/assessment.py`)

```
id                        PK

teaching_assignment_id    FK teaching_assignments, NOT NULL, indexed   <- the anchor

faculty_id                FK faculty,      NOT NULL, indexed  \
subject_id                FK subjects,     NOT NULL, indexed   |  denormalized from the
section_id                FK sections,     NOT NULL, indexed   |  assignment at write time,
semester_id               FK semesters,    NOT NULL, indexed  /   never accepted from client

assessment_type           VARCHAR(30)  NOT NULL, indexed
name                      VARCHAR(255) NOT NULL
sequence_no               INTEGER      NOT NULL, default 1
description               VARCHAR(1000) NULL

max_marks                 FLOAT        NOT NULL          -- > 0
weightage_percent         FLOAT        NOT NULL          -- share of the subject's 100
pass_marks                FLOAT        NULL              -- defaults to PASS_PERCENT of max

scheduled_date            DATE         NULL, indexed
duration_minutes          INTEGER      NULL

status                    VARCHAR(20)  NOT NULL, default 'DRAFT', indexed

created_by_user_id        FK users     NOT NULL, indexed
published_at              DATETIME     NULL
locked_by_user_id         FK users     NULL
locked_at                 DATETIME     NULL

is_active                 BOOLEAN      NOT NULL, default True
created_at / updated_at   DATETIME     server_default / onupdate
```

Constraint:

```
UNIQUE (teaching_assignment_id, assessment_type, sequence_no)
    name = uq_assessment_assignment_type_seq
```

Two tabs creating "Internal 1" for the same class must not both succeed. The
service reports the duplicate with the subject and the component name; the
constraint is the backstop.

Relationships:

```python
records = relationship("MarkRecord", back_populates="assessment",
                       cascade="all, delete-orphan")
```

**Deliberately NO `back_populates` on `TeachingAssignment`.** `Section` already
cascades delete-orphan into `teaching_assignments`, which cascades into
`timetable_entries`. Adding a fourth link would extend that cascade into exam
history, so deleting a section would silently destroy every mark it ever
received. This is the identical reasoning recorded on
`AttendanceSession.records` — see the comment in
`app/models/attendance_session.py`. Assessments are protected the same way
attendance is: explicit count guards in the service, not ORM cascade.

### 3.2 `MarkRecord` (`app/models/mark_record.py`)

```
id                        PK
assessment_id             FK assessments, NOT NULL, indexed
student_id                FK students,    NOT NULL, indexed
section_id                FK sections,    NOT NULL, indexed   <- denormalized, see below

marks_obtained            FLOAT        NULL                   <- NULL means "not entered"
is_absent                 BOOLEAN      NOT NULL, default False
is_malpractice            BOOLEAN      NOT NULL, default False
remarks                   VARCHAR(500) NULL

entered_by_user_id        FK users     NOT NULL, indexed
entered_at                DATETIME     NOT NULL

is_active                 BOOLEAN      NOT NULL, default True
created_at / updated_at
```

Constraint:

```
UNIQUE (assessment_id, student_id)
    name = uq_mark_record_assessment_student
```

`section_id` is denormalized from the student at write time, for the same
reason `AttendanceRecord` does it: a student who transfers mid-semester keeps
their earlier marks attached to the section that actually taught them.

`entered_by_user_id` is rewritten on every save, so it means "last corrected
by" — which is what an audit actually needs.

---

## 4. Constants (`app/schemas/assessment.py`)

Following the precedent of `ATTENDANCE_STATUSES` / `DEFAULT_ATTENDANCE_THRESHOLD`,
every institutional policy value is a named constant at module top, so a college
with a different scheme changes one file.

```python
ASSESSMENT_TYPES = ["INTERNAL", "ASSIGNMENT", "LAB", "QUIZ", "MODEL", "EXTERNAL"]

# DRAFT   - being prepared; invisible to students, excluded from every aggregate
# PUBLISHED - marks visible to students and counted
# LOCKED  - frozen; faculty can no longer write, admin may unlock (audited)
ASSESSMENT_STATUSES = ["DRAFT", "PUBLISHED", "LOCKED"]

DEFAULT_ASSESSMENT_STATUS = "DRAFT"

# Total weightage a single teaching assignment may allocate.
MAX_TOTAL_WEIGHTAGE = 100.0

# Below this percentage of an assessment's max_marks, a student has failed it.
PASS_PERCENT = 40.0

# 10-point scale. (minimum percent, letter, grade point).
# Ordered high to low; the first band whose minimum is met wins.
GRADE_SCALE = [
    (90.0, "O",  10.0),
    (80.0, "A+",  9.0),
    (70.0, "A",   8.0),
    (60.0, "B+",  7.0),
    (55.0, "B",   6.0),
    (50.0, "C",   5.0),
    (40.0, "P",   4.0),
    (0.0,  "F",   0.0),
]

# Attendance below this is *reported* alongside a result, never used to
# withhold it. See section 6, decision D2.
RESULT_ATTENDANCE_FLAG_THRESHOLD = 75.0
```

---

## 5. Rules the service owns

These are the reason this is a module and not CRUD. Each one has a test.

1. **`max_marks > 0`.** It is the denominator of every percentage this module
   produces; zero makes the whole subject unreadable.

2. **Weightage never exceeds 100 per teaching assignment.** Creating or editing
   an assessment sums the weightage of every other active assessment on the
   same assignment. On reject the error names what consumes the budget:

   > `Internal 1 (30%) and Assignment 1 (20%) already allocate 50% of CS301 /
   > Section A. 50% remains; 60% was requested.`

   A bare "invalid weightage" makes the user guess. Naming the consumers is the
   difference between a usable system and a frustrating one.

3. **Marks are bounded:** `0 <= marks_obtained <= max_marks`. Rejected with the
   student's name and the ceiling, not a field-level code.

4. **Absent means null.** `is_absent = True` requires `marks_obtained is None`.
   Absent counts as 0 in aggregation but is reported as its own count, because
   "twelve absentees" and "twelve zeros" are different facts about a class.

5. **NULL is not zero.** "Not entered" is the **absence of a row**, not a row
   holding NULL and not a row holding 0. A row exists only once somebody has
   said something about that student — a mark, an absence, or a malpractice
   case — so clearing a mark deletes the row and returns the student to
   pending. That keeps "we do not know" expressible in exactly one way.
   (Refined during step 3; the model still permits NULL, which is what an
   absence and a malpractice case store.) An unentered mark leaves the
   assessment *incomplete*.
   An incomplete assessment excludes its subject from result computation
   entirely — it must never quietly score a student 0. This is the single most
   important invariant in the module.

6. **Roster comes from the section's ACTIVE students** at sheet-build time,
   while nothing that *reads* saved marks filters on status. A student
   suspended in November keeps their October marks. Identical to the attendance
   rule, and for the identical reason.

7. **Faculty are scoped to their own teaching assignments.** Admin is not.
   Reuse the department-scope helper pattern from
   `app/routers/attendance.py::_department_scope_for`.

8. **`LOCKED` blocks faculty writes.** Only an admin unlocks. Locking stamps
   `locked_by_user_id` / `locked_at`; unlocking returns the status to
   `PUBLISHED` and **leaves that stamp in place**, so the row still shows it
   was locked, by whom and when. An admin is never blocked by the freeze —
   correcting a frozen sheet is exactly what the admin is for.

8a. **Publishing requires marks on file.** A published component with no marks
    contributes an empty column to every result it touches and reads as a
    system fault rather than an empty sheet. (Added during step 2.)

8b. **`max_marks` can never fall below a mark already awarded**, which would
    put a student above full marks and over 100%. The rejection names the mark
    that blocks it. An unset `pass_marks` re-derives when `max_marks` changes
    rather than going stale. (Added during step 2.)

9. **DRAFT is invisible to students** and excluded from every aggregate,
   distribution and dashboard figure. Publishing is the deliberate act that
   makes a mark real.

10. **Saving a mark sheet corrects it, never duplicates it.** Bulk upsert,
    all-or-nothing in one transaction. Same semantics as the attendance sheet.

11. **Deleting an assessment that has marks requires admin and explicit
    `force=true`**, and the error states how many records the deletion
    destroys before it is confirmed.

12. **SGPA is computed only when complete.** If any credit-bearing subject in
    the section/semester lacks a final grade, the payload carries
    `has_data: false` and the UI renders an empty state. A partial SGPA is
    worse than none: it will be screenshotted and believed. This follows the
    rule already stated at the top of `app/schemas/stats.py` — *a zero must
    never stand in for "we do not know"*.

### 5.1 Computation

For one student, one subject, one section:

```
subject_percent = sum over PUBLISHED|LOCKED assessments of
                      (effective_marks / max_marks) * weightage_percent
                  --------------------------------------------------------
                                sum of weightage_percent

effective_marks = 0.0 if (is_absent or is_malpractice) else marks_obtained
```

Dividing by the *allocated* weightage rather than by 100 means a subject that
has run two of its three components reports an honest percentage of what has
happened so far, instead of appearing to have failed the missing third.

`grade_letter`, `grade_point` come from the first `GRADE_SCALE` band whose
minimum `subject_percent` meets.

```
SGPA = sum(grade_point * subject.credits) / sum(subject.credits)
```

over credit-bearing subjects only, and only when rule 12 is satisfied.

---

## 6. Decisions

**D1 — Grade scale.** 10-point O..F, 40% pass, as in `GRADE_SCALE` above.
Assumed, not confirmed. It is one constant list; change it there and nowhere
else.

**D2 — Attendance shortage does not block a result.** The result payload
carries `attendance_percent` and `attendance_short: bool` against
`RESULT_ATTENDANCE_FLAG_THRESHOLD`, and the UI shows the flag. Withholding a
result is an administrative decision with an appeals process behind it; a
service that enforces it silently produces a support ticket, not a policy.

**D3 — No stored grades.** Section 2.

**D6 — The dashboard does not recompute grades.** `collect_assessments` calls
`results_service.subject_result`, so the dashboard and the result screen can
never disagree, and the rules results enforces (drafts reach nobody, an
incomplete sheet has no grade) hold there for free. (Decided during step 6.)

**D5 — A mark sheet has no per-record endpoint.** The sheet is the unit of
work, so `/api/marks/sheet` is the only write path and a `MarkRecord` is never
addressed by its own id. Entries omitted from a save are left untouched, which
is what makes entering a sheet across several sittings safe. (Decided during
step 3.)

**D4 — `AssessmentUpdate` carries no `teaching_assignment_id`.** Moving an
assessment to another class would strand entered marks against a roster that
never sat it. That operation is a delete and a create, and it should look like
one. (Decided during step 1.)

---

## 7. API surface

Named to parallel attendance, so the frontend service modules stay predictable.

### Assessments — `/api/assessments`

```
GET    /options                 types, statuses, grade scale, MAX_TOTAL_WEIGHTAGE
GET    /                        filter: semester, section, subject, faculty, type, status
GET    /{id}
POST   /                        admin, or the owning faculty member
PATCH  /{id}                    partial; PUT would make an omitted field mean "clear it"
PATCH  /{id}/status             publish | lock | unlock
DELETE /{id}                    ?force=true when marks exist; admin only
GET    /{id}/weightage          remaining budget on this assignment, with consumers
```

### Marks — `/api/marks`

```
GET    /sheet?assessment_id=    roster + saved marks + draft rows for unentered students
POST   /sheet                   bulk upsert, all-or-nothing
GET    /my-assessments          faculty: mine, each with entered/total progress
```

`/my-assessments` is what makes the module feel finished. A faculty member
opens their dashboard and sees

> Internal 2 · CS301 · Section A · **38 of 52 entered** · closes Friday

rather than an empty dropdown they must fill in before anything appears.

### Results — `/api/results`

```
GET    /subject?section_id=&subject_id=    distribution, pass rate, high/low/mean
GET    /section?section_id=                full mark sheet: students x subjects
GET    /student?student_id=                admin / dept-scoped faculty
GET    /me                                 the signed-in student, PUBLISHED only
```

All four return `has_data: false` with an explanatory `reason` rather than
zeros when the underlying marks are incomplete.

---

## 8. Frontend

| route | role | mirrors |
| --- | --- | --- |
| `/admin/assessments` | admin | `pages/admin/subjects/` + `components/subjects/` |
| `/admin/results` | admin | `components/charts/` — `DonutChart` for grade distribution, `BarList` for subject pass rates |
| `/faculty/marks` | faculty | `pages/faculty/attendance/MarkAttendance.jsx` |
| student results panel | student | `components/attendance/MyAttendance.jsx` |

New components:

```
components/assessments/   AssessmentFilters, AssessmentForm, AssessmentTable,
                          AssessmentDetails, WeightageBar
components/marks/         MarkSheetPanel, MarkSheetTable, MyResults,
                          SubjectResultTable, GradeDistribution
services/                 assessmentService.js, marksService.js, resultsService.js
```

### The mark sheet is the whole UX

Marks entry is a hundred-keystroke task. Treating it as a form with a Save
button is what makes these systems hated. `MarkSheetTable` must have:

- **keyboard-first entry** — Enter and Down move to the next student in the
  column; Up moves back; the cell is focused, not the row;
- **inline validation before save** — a value over `max_marks` flags on the
  cell as it is typed, not on submit after ninety other entries;
- **absent as a one-key toggle**, which clears and disables the marks cell;
- **a dirty-state guard** on navigation away;
- **visible progress** — "38 / 52 entered" in the panel header, matching what
  `/my-assessments` reported.

`WeightageBar` shows the assignment's 100% budget with the existing components
as filled segments, so the constraint in rule 2 is visible *before* the form is
submitted rather than explained by an error afterwards.

Every panel goes through the existing `hooks/useAsyncPanel.js`. Admin routes
must be registered in the `adminRoutes` array in `src/App.jsx` — a link to a
path not in that array falls through the catch-all and signs the user out,
which is recorded in the comment on `adminRoutePaths`.

---

## 9. Build order

Steps 2, 3 and 4 are strictly sequential. Step 5 may begin once step 3 lands.

| # | step | deliverable |
| --- | --- | --- |
| 1 | Models, schemas, constants | **Done.** `models/assessment.py`, `models/mark_record.py`, `schemas/assessment.py`, `schemas/marks.py`, `schemas/result.py`. Tables auto-create through `create_db_and_tables()`; no migration tooling in this project. |
| 2 | `assessment_service.py` + router | **Done.** CRUD, weightage ledger, status transitions, faculty scoping, delete guard, plus assessment guards added to the section and teaching-assignment delete routes. `tests/test_assessments.py` — 29 tests |
| 3 | `marks_service.py` + router | sheet build, bulk upsert, bounds, absent/malpractice, progress. `tests/test_marks.py` |
| 4 | `results_service.py` + router | **Done.** Weighted aggregation, grade bands, SGPA with the completeness gate, attendance flag, section and subject reports. `tests/test_results.py` — 21 tests |
| 5 | Frontend | **Done.** `services/assessmentService.js`, `components/assessments/*`, `components/marks/*`, `/admin/assessments`, `/admin/results`, `/faculty/marks`, `MyResults` on the student dashboard, sidebar + `adminRoutes` entries, and the styles for all of it. |
| 6 | Stats integration | **Done.** The prohibition list in `schemas/stats.py` is amended (marks are no longer fabrication; CGPA, deltas and forecasts still are), `AssessmentStats` added to the dashboard payload, and grade-distribution + weakest-subject panels added to the admin dashboard. 3 new tests in `test_stats.py`. |

Register all three routers in `app/main.py` under `/api/assessments`,
`/api/marks`, `/api/results`.

Rough scale, in line with the attendance module's footprint: ~1,100 lines of
service, ~600 of router and schema, ~1,800 of tests, ~1,400 of React.

---

## 10. Test plan

`tests/conftest.py` already points the suite at a throwaway database and builds
the full schema, so new test modules need no setup beyond fixtures.

Per the existing suites, each module covers auth/role matrix, validation, and
the integrity rules by name.

**`test_assessments.py`**
- weightage: exactly 100 accepted; 100.01 rejected; edit that would overflow
  rejected; edit that stays within budget accepted; the error names consumers
- `max_marks <= 0` rejected
- duplicate `(assignment, type, sequence_no)` returns 409
- faculty may create on their own assignment, 403 on another's
- status transitions: DRAFT->PUBLISHED->LOCKED; faculty write on LOCKED is 403;
  admin unlock succeeds and stamps `locked_by` / `locked_at`
- delete with marks without `force` is 409 and states the record count;
  with `force` as admin succeeds; as faculty is 403
- **deleting a section does not delete its assessments** (the cascade guard)

**`test_marks.py`**
- sheet roster is the section's ACTIVE students; a suspended student's *saved*
  marks still read back
- `marks > max_marks` and `marks < 0` rejected, naming the student
- `is_absent` with a non-null mark rejected
- save twice corrects rather than duplicates; unique constraint holds under a
  simulated double submit
- partial save leaves the rest NULL, and NULL reads back as "not entered", not 0
- faculty scoping; LOCKED blocks entry
- `/my-assessments` progress counts match the sheet

**`test_results.py`**
- weighted percentage across two components of unequal weightage
- absent contributes 0 to the numerator but is counted separately
- a subject with an incomplete assessment is excluded, with `has_data: false`
  and a reason
- DRAFT assessments never appear in any aggregate or in `/me`
- every `GRADE_SCALE` boundary, including both sides of 40.0
- SGPA correct with mixed credits; withheld when any subject is incomplete
- `attendance_short` flags below threshold but does not suppress the result
- a student reading `/me` sees only their own published marks

---

## 11. Explicitly out of scope

Recorded here so they are not smuggled in:

- **stored or frozen results** — a `SemesterResult` snapshot is a later phase
- **transcripts, PDFs, printed mark sheets** — an export concern, not this module
- **re-evaluation / revaluation workflow** — needs a request-and-approval model
- **backlog and supplementary exams** — needs attempt history on the record
- **exam seating, hall tickets, invigilator duty** — a separate scheduling module
- **any dashboard figure not derived from a PUBLISHED mark**
- **CGPA** — nothing stores a prior semester, so it would be fabrication
