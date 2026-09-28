import {
  STATUS_CLASS,
  STATUS_LABEL,
  TYPE_LABEL,
  formatDateValue,
} from '../../services/assessmentService';

/**
 * One row per component, with its entry progress on the row itself.
 *
 * "38 of 52 entered" is the number the person came to the screen for, so it
 * is rendered here rather than behind a click.
 */
export default function AssessmentTable({
  rows,
  loading,
  onEdit,
  onEnterMarks,
  onStatus,
  onDelete,
}) {
  if (loading) return <p className="empty-note">Loading assessments…</p>;
  if (!rows.length) {
    return (
      <p className="empty-note">
        No assessments match these filters. Create one against a teaching assignment to begin.
      </p>
    );
  }

  return (
    <div className="department-table-wrap scroll-table">
      <table className="department-table">
        <thead>
          <tr>
            <th>Assessment</th>
            <th>Subject</th>
            <th>Section</th>
            <th>Out of</th>
            <th>Weight</th>
            <th>Entry</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const progress = row.total_students
              ? Math.round((row.entered_count / row.total_students) * 100)
              : 0;

            return (
              <tr key={row.id} className={row.is_active ? '' : 'is-muted'}>
                <td>
                  <div className="dept-name">{row.name}</div>
                  <span className="type-chip">{TYPE_LABEL[row.assessment_type] || row.assessment_type}</span>
                  {row.scheduled_date && (
                    <span className="page-subtitle"> {formatDateValue(row.scheduled_date)}</span>
                  )}
                </td>
                <td>
                  <div className="mono">{row.subject_code}</div>
                  <div className="page-subtitle">{row.subject_name}</div>
                </td>
                <td>
                  {row.section_name}
                  <div className="page-subtitle">{row.faculty_name}</div>
                </td>
                <td className="mono">{row.max_marks}</td>
                <td className="mono">{row.weightage_percent}%</td>
                <td>
                  <div className="coverage-bar">
                    <div
                      className="coverage-bar-fill"
                      style={{
                        width: `${progress}%`,
                        background: row.is_complete
                          ? 'var(--chart-series-1)'
                          : 'var(--accent-amber)',
                      }}
                    />
                  </div>
                  <span className="page-subtitle">
                    {row.entered_count} of {row.total_students} entered
                  </span>
                </td>
                <td>
                  <span className={`status-badge ${STATUS_CLASS[row.status] || ''}`}>
                    {STATUS_LABEL[row.status] || row.status}
                  </span>
                  {!row.is_active && <span className="status-badge inactive">Inactive</span>}
                </td>
                <td>
                  <div className="action-buttons">
                    <button type="button" className="table-btn success-btn" onClick={() => onEnterMarks(row)}>
                      Marks
                    </button>
                    <button type="button" className="table-btn edit-btn" onClick={() => onEdit(row)}>
                      Edit
                    </button>
                    {row.status === 'DRAFT' && (
                      <button type="button" className="table-btn" onClick={() => onStatus(row, 'publish')}>
                        Publish
                      </button>
                    )}
                    {row.status === 'PUBLISHED' && (
                      <button type="button" className="table-btn warn-btn" onClick={() => onStatus(row, 'lock')}>
                        Lock
                      </button>
                    )}
                    {row.status === 'LOCKED' && (
                      <button type="button" className="table-btn warn-btn" onClick={() => onStatus(row, 'unlock')}>
                        Unlock
                      </button>
                    )}
                    <button type="button" className="table-btn delete-btn" onClick={() => onDelete(row)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
