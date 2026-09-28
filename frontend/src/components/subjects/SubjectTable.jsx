export default function SubjectTable({
  subjects,
  loading,
  hasFilters,
  sort,
  onSort,
  onView,
  onEdit,
  onToggleStatus,
  onDelete,
  busyRowId,
}) {
  const indicator = (key) => (sort.key !== key ? '' : sort.direction === 'asc' ? ' ▲' : ' ▼');

  const column = (key, label) => (
    <th className="sortable" onClick={() => onSort(key)}>{label}{indicator(key)}</th>
  );

  return (
    <div className="department-table-wrap scroll-table">
      <table className="department-table faculty-table">
        <thead>
          <tr>
            {column('subject_code', 'Code')}
            {column('name', 'Subject')}
            {column('course_code', 'Course')}
            {column('semester_number', 'Semester')}
            {column('subject_type', 'Type')}
            {column('credits', 'Credits')}
            <th>L–T–P</th>
            {column('is_active', 'Status')}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan="9" className="table-loading">Loading subjects...</td></tr>
          ) : subjects.length === 0 ? (
            <tr>
              <td colSpan="9" className="table-empty">
                {hasFilters
                  ? 'No subjects match the current filters.'
                  : 'No subjects yet. Use “+ Add Subject” to create the first one.'}
              </td>
            </tr>
          ) : (
            subjects.map((item) => (
              <tr key={item.id} className={item.is_active ? '' : 'row-inactive'}>
                <td className="mono">{item.subject_code}</td>
                <td>
                  <button type="button" className="link-btn dept-name" onClick={() => onView(item)}>
                    {item.name}
                  </button>
                  {item.description && <div className="dept-desc">{item.description}</div>}
                </td>
                <td>
                  <div>{item.course_code || '—'}</div>
                  <div className="dept-desc">{item.department_code || ''}</div>
                </td>
                <td>{item.semester_number ?? '—'}</td>
                <td><span className={`type-chip type-${item.subject_type.toLowerCase()}`}>{item.subject_type}</span></td>
                <td>{item.credits}</td>
                <td className="mono">
                  {item.lecture_hours}–{item.tutorial_hours}–{item.practical_hours}
                  <div className="dept-desc">{item.total_hours} hrs/week</div>
                </td>
                <td>
                  <span className={`status-badge ${item.is_active ? 'active' : 'inactive'}`}>
                    {item.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>
                  <div className="action-buttons">
                    <button type="button" className="table-btn view-btn" onClick={() => onView(item)}>View</button>
                    <button type="button" className="table-btn edit-btn" onClick={() => onEdit(item)}>Edit</button>
                    <button
                      type="button"
                      className={`table-btn ${item.is_active ? 'warn-btn' : 'success-btn'}`}
                      onClick={() => onToggleStatus(item)}
                      disabled={busyRowId === item.id}
                    >
                      {item.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      type="button"
                      className="table-btn delete-btn"
                      onClick={() => onDelete(item)}
                      disabled={busyRowId === item.id}
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
