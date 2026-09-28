import { toDateValue } from '../../services/attendanceService';

/**
 * Department → Course → Semester → Section, plus a subject and a date range.
 * Changing a level clears everything below it, exactly as the timetable scope
 * picker does.
 */
export default function AttendanceFilters({
  filters,
  departments,
  courses,
  semesters,
  sections,
  subjects,
  requireSection = false,
  onChange,
  onReset,
}) {
  const change = (key) => (e) => onChange(key, e.target.value);
  const activeCount = Object.values(filters).filter(Boolean).length;

  return (
    <div className="filter-bar attendance-filter-bar">
      <select className="department-search" value={filters.department_id} onChange={change('department_id')}>
        <option value="">All Departments</option>
        {departments.map((item) => (
          <option key={item.id} value={item.id}>{item.name} ({item.code})</option>
        ))}
      </select>

      <select className="department-search" value={filters.course_id} onChange={change('course_id')}>
        <option value="">All Courses</option>
        {courses.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={filters.semester_id}
        onChange={change('semester_id')}
        disabled={!filters.course_id}
      >
        <option value="">{filters.course_id ? 'All Semesters' : 'Pick a course first'}</option>
        {semesters.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={filters.section_id}
        onChange={change('section_id')}
        disabled={!filters.semester_id}
      >
        <option value="">
          {!filters.semester_id
            ? 'Pick a semester first'
            : requireSection ? 'Select a section' : 'All Sections'}
        </option>
        {sections.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={filters.subject_id}
        onChange={change('subject_id')}
        disabled={!filters.semester_id}
      >
        <option value="">{filters.semester_id ? 'All Subjects' : 'Pick a semester first'}</option>
        {subjects.map((item) => (
          <option key={item.id} value={item.id}>{item.subject_code} — {item.name}</option>
        ))}
      </select>

      <label className="attendance-date">
        From
        <input type="date" value={filters.from_date} max={toDateValue()} onChange={change('from_date')} />
      </label>

      <label className="attendance-date">
        To
        <input type="date" value={filters.to_date} max={toDateValue()} onChange={change('to_date')} />
      </label>

      <button type="button" className="secondary-btn filter-reset" onClick={onReset} disabled={!activeCount}>
        Clear
      </button>
    </div>
  );
}
