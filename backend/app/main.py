from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import create_db_and_tables
from app.routers import (
    academic_years,
    assessments,
    attendance,
    auth,
    courses,
    departments,
    faculty,
    marks,
    sections,
    results,
    semesters,
    stats,
    students,
    subjects,
    teaching_assignments,
    time_slots,
    timetable,
)

app = FastAPI(title="Smart College System API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|172\.\d+\.\d+\.\d+):(517[0-9]|4173|3000)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    create_db_and_tables()


@app.get("/")
def read_root():
    return {"message": "Smart College API is running"}


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(departments.router, prefix="/api/departments", tags=["departments"])
app.include_router(courses.router, prefix="/api/courses", tags=["courses"])
app.include_router(academic_years.router, prefix="/api/academic-years", tags=["academic-years"])
app.include_router(semesters.router, prefix="/api/semesters", tags=["semesters"])
app.include_router(sections.router, prefix="/api/sections", tags=["sections"])
app.include_router(faculty.router, prefix="/api/faculty", tags=["faculty"])
app.include_router(students.router, prefix="/api/students", tags=["students"])
app.include_router(subjects.router, prefix="/api/subjects", tags=["subjects"])
app.include_router(
    teaching_assignments.router,
    prefix="/api/teaching-assignments",
    tags=["teaching-assignments"],
)
app.include_router(time_slots.router, prefix="/api/time-slots", tags=["time-slots"])
app.include_router(timetable.router, prefix="/api/timetable", tags=["timetable"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["attendance"])
app.include_router(assessments.router, prefix="/api/assessments", tags=["assessments"])
app.include_router(marks.router, prefix="/api/marks", tags=["marks"])
app.include_router(results.router, prefix="/api/results", tags=["results"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
