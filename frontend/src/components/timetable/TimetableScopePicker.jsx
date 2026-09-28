/**
 * Department → Course → Semester → Section. The grid is scoped to exactly one
 * section, because that is the unit the (section, day, period) uniqueness is
 * defined over — one section's week is the only view where every cell holds
 * at most one class.
 */
export default function TimetableScopePicker({
  scope,
  departments,
  courses,
  semesters,
  sections,
  showWeekend,
  onChange,
  onToggleWeekend,
  onReset,
}) {
  const change = (key) => (e) => onChange(key, e.target.value);
  const activeCount = Object.values(scope).filter(Boolean).length;

  return (
    <div className="filter-bar timetable-scope-bar">
      <select className="department-search" value={scope.department_id} onChange={change('department_id')}>
        <option value="">All Departments</option>
        {departments.map((item) => (
          <option key={item.id} value={item.id}>{item.name} ({item.code})</option>
        ))}
      </select>

      <select className="department-search" value={scope.course_id} onChange={change('course_id')}>
        <option value="">Select Course</option>
        {courses.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={scope.semester_id}
        onChange={change('semester_id')}
        disabled={!scope.course_id}
      >
        <option value="">
          {!scope.course_id
            ? 'Select a course first'
            : semesters.length ? 'Select Semester' : 'No semesters for this course'}
        </option>
        {semesters.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={scope.section_id}
        onChange={change('section_id')}
        disabled={!scope.semester_id}
      >
        <option value="">
          {!scope.semester_id
            ? 'Select a semester first'
            : sections.length ? 'Select Section' : 'No sections in this semester'}
        </option>
        {sections.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}{item.room_number ? ` (${item.room_number})` : ''}
          </option>
        ))}
      </select>

      <label className="checkbox-row">
        <input type="checkbox" checked={showWeekend} onChange={onToggleWeekend} />
        <span>Show Sun</span>
      </label>

      <button type="button" className="secondary-btn filter-reset" onClick={onReset} disabled={!activeCount}>
        Clear
      </button>
    </div>
  );
}
