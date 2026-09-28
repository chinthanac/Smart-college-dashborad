/**
 * Search plus the Department → Course → Semester → {Subject, Section} chain.
 * Clearing a level clears everything below it.
 */
export default function TeachingAssignmentFilters({
  search,
  onSearchChange,
  filters,
  onFilterChange,
  departments,
  courses,
  semesters,
  subjects,
  sections,
  activeFilterCount,
  onReset,
}) {
  return (
    <div className="filter-bar assignment-filter-bar">
      <input
        className="department-search filter-search"
        type="search"
        placeholder="Search by subject, faculty name or ID, or section..."
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
      />

      <select
        className="department-search"
        value={filters.department_id}
        onChange={(e) => onFilterChange('department_id', e.target.value)}
      >
        <option value="">All Departments</option>
        {departments.map((item) => (
          <option key={item.id} value={item.id}>{item.name} ({item.code})</option>
        ))}
      </select>

      <select
        className="department-search"
        value={filters.course_id}
        onChange={(e) => onFilterChange('course_id', e.target.value)}
      >
        <option value="">All Courses</option>
        {courses.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={filters.semester_id}
        onChange={(e) => onFilterChange('semester_id', e.target.value)}
        disabled={!filters.course_id}
      >
        <option value="">{filters.course_id ? 'All Semesters' : 'All Semesters (pick a course)'}</option>
        {semesters.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={filters.subject_id}
        onChange={(e) => onFilterChange('subject_id', e.target.value)}
        disabled={!filters.semester_id}
      >
        <option value="">{filters.semester_id ? 'All Subjects' : 'All Subjects (pick a semester)'}</option>
        {subjects.map((item) => (
          <option key={item.id} value={item.id}>{item.subject_code} — {item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={filters.section_id}
        onChange={(e) => onFilterChange('section_id', e.target.value)}
        disabled={!filters.semester_id}
      >
        <option value="">{filters.semester_id ? 'All Sections' : 'All Sections (pick a semester)'}</option>
        {sections.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select
        className="department-search"
        value={filters.is_active}
        onChange={(e) => onFilterChange('is_active', e.target.value)}
      >
        <option value="">All Statuses</option>
        <option value="true">Active only</option>
        <option value="false">Inactive only</option>
      </select>

      <button type="button" className="secondary-btn filter-reset" onClick={onReset} disabled={!activeFilterCount}>
        Clear{activeFilterCount ? ` (${activeFilterCount})` : ''}
      </button>
    </div>
  );
}
