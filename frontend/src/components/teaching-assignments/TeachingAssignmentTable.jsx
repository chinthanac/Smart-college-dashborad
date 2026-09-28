export default function TeachingAssignmentTable({
  assignments,
  loading,
  hasFilters,
  sort,
  onSort,
  onView,
  onReassign,
  onEdit,
  onToggleStatus,
  onDelete,
  busyRowId,
}) {
  const indicator = (key) => (sort.key !== key ? '' : sort.direction === 'asc' ? ' ▲' : ' ▼');

  const column = (key, label) => (
    <th className="sortable" onClick={() => onSort(key)}>{label}{indicator(key)}</th>
  );

  // Deactivating a subject, section or faculty deliberately does not cascade,
  // so surface it here — this is how an admin finds a stale assignment.
  const staleReason = (item) => {
    const stale = [
      item.subject_is_active === false && 'subject',
      item.section_is_active === false && 'section',
      item.faculty_is_active === false && 'faculty',
    ].filter(Boolean);
    return stale.length ? `Inactive ${stale.join(', ')}` : null;
  };

  return (
    <div className="department-table-wrap scroll-table">
      <table className="department-table faculty-table">
        <thead>
          <tr>
            {column('subject_code', 'Subject')}
            {column('course_code', 'Course')}
            {column('semester_number', 'Semester')}
            {column('section_name', 'Section')}
            {column('faculty_name', 'Faculty')}
            {column('is_active', 'Status')}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan="7" className="table-loading">Loading teaching assignments...</td></tr>
          ) : assignments.length === 0 ? (
            <tr>
              <td colSpan="7" className="table-empty">
                {hasFilters
                  ? 'No teaching assignments match the current filters.'
                  : 'No teaching assignments yet. Use “+ Assign Subject” to create the first one.'}
              </td>
            </tr>
          ) : (
            assignments.map((item) => {
              const stale = staleReason(item);
              return (
                <tr key={item.id} className={item.is_active ? '' : 'row-inactive'}>
                  <td>
                    <button type="button" className="link-btn dept-name" onClick={() => onView(item)}>
                      {item.subject_name}
                    </button>
                    <div className="dept-desc mono">{item.subject_code}</div>
                  </td>
                  <td>
                    <div>{item.course_code || '—'}</div>
                    <div className="dept-desc">{item.department_code || ''}</div>
                  </td>
                  <td>{item.semester_number ?? '—'}</td>
                  <td>
                    <div>{item.section_name || '—'}</div>
                    <div className="dept-desc">{item.section_room_number || ''}</div>
                  </td>
                  <td>
                    <div>{item.faculty_name || '—'}</div>
                    <div className="dept-desc">
                      <span className="mono">{item.faculty_code}</span>
                      {item.faculty_designation ? ` · ${item.faculty_designation}` : ''}
                    </div>
                    {item.is_cross_department && (
                      <span className="type-chip type-cross-dept" title={`Faculty is in ${item.faculty_department_name}`}>
                        CROSS-DEPT
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`status-badge ${item.is_active ? 'active' : 'inactive'}`}>
                      {item.is_active ? 'Active' : 'Inactive'}
                    </span>
                    {stale && <div className="dept-desc stale-warning">{stale}</div>}
                  </td>
                  <td>
                    <div className="action-buttons">
                      <button type="button" className="table-btn view-btn" onClick={() => onView(item)}>View</button>
                      <button type="button" className="table-btn edit-btn" onClick={() => onReassign(item)}>Reassign</button>
                      <button type="button" className="table-btn neutral-btn" onClick={() => onEdit(item)}>Edit</button>
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
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
