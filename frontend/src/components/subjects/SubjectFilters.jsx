/**
 * Search + the dependent Course → Semester chain.
 * Semesters are fetched for the selected course only, so an invalid
 * course/semester pair can never be assembled here.
 */
export default function SubjectFilters({
  search,
  onSearchChange,
  filters,
  onFilterChange,
  departments,
  courses,
  semesters,
  subjectTypes,
  activeFilterCount,
  onReset,
}) {
  return (
    <div className="filter-bar subject-filter-bar">
      <input
        className="department-search filter-search"
        type="search"
        placeholder="Search by subject code, name, or description..."
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
        value={filters.subject_type}
        onChange={(e) => onFilterChange('subject_type', e.target.value)}
      >
        <option value="">All Types</option>
        {subjectTypes.map((item) => (
          <option key={item} value={item}>{item}</option>
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
