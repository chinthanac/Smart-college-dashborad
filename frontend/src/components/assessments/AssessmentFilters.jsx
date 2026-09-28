import {
  ASSESSMENT_STATUSES,
  ASSESSMENT_TYPES,
  STATUS_LABEL,
  TYPE_LABEL,
} from '../../services/assessmentService';

export default function AssessmentFilters({
  chain,
  filters,
  onChange,
  onReset,
  search,
  onSearchChange,
}) {
  const set = (key) => (event) => onChange(key, event.target.value);

  return (
    <div className="filters-row">
      <input
        className="search-input"
        placeholder="Search by name, subject or section"
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
      />

      <select value={filters.department_id} onChange={set('department_id')}>
        <option value="">All departments</option>
        {chain.departments.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select value={filters.course_id} onChange={set('course_id')}>
        <option value="">All courses</option>
        {chain.courses.map((item) => (
          <option key={item.id} value={item.id}>{item.code} — {item.name}</option>
        ))}
      </select>

      <select value={filters.semester_id} onChange={set('semester_id')}>
        <option value="">All semesters</option>
        {chain.semesters.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select value={filters.section_id} onChange={set('section_id')} disabled={!chain.sections.length}>
        <option value="">All sections</option>
        {chain.sections.map((item) => (
          <option key={item.id} value={item.id}>{item.name}</option>
        ))}
      </select>

      <select value={filters.assessment_type} onChange={set('assessment_type')}>
        <option value="">All types</option>
        {ASSESSMENT_TYPES.map((type) => (
          <option key={type} value={type}>{TYPE_LABEL[type]}</option>
        ))}
      </select>

      <select value={filters.status} onChange={set('status')}>
        <option value="">All statuses</option>
        {ASSESSMENT_STATUSES.map((status) => (
          <option key={status} value={status}>{STATUS_LABEL[status]}</option>
        ))}
      </select>

      <button type="button" className="table-btn" onClick={onReset}>Reset</button>
    </div>
  );
}
