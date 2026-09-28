import { formatDateValue } from '../../services/attendanceService';

/** The register log: every class that has been marked. */
export default function SessionTable({ sessions, loading, busyId, onOpen, onCancel, onDelete }) {
  if (loading) {
    return (
      <div className="department-table-wrap scroll-table">
        <p className="table-loading">Loading registers...</p>
      </div>
    );
  }

  if (!sessions.length) {
    return (
      <p className="empty-note">
        No attendance has been marked for this filter yet.
      </p>
    );
  }

  return (
    <div className="department-table-wrap scroll-table">
      <table className="department-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Class</th>
            <th>Section</th>
            <th>Faculty</th>
            <th>Attendance</th>
            <th>Marked By</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((item) => (
            <tr key={item.id} className={item.is_cancelled ? 'row-inactive' : ''}>
              <td>
                <div className="dept-name">{formatDateValue(item.class_date)}</div>
                <div className="dept-desc">{item.day_name} · {item.slot_name}</div>
              </td>
              <td>
                <div className="dept-name">{item.subject_name}</div>
                <div className="dept-desc mono">{item.subject_code}</div>
              </td>
              <td>{item.section_name}</td>
              <td>{item.faculty_name}</td>
              <td>
                {item.is_cancelled ? (
                  <>
                    <span className="status-badge inactive">Cancelled</span>
                    <div className="dept-desc">{item.cancel_reason}</div>
                  </>
                ) : (
                  <>
                    <strong>{item.attendance_percentage}%</strong>
                    <div className="dept-desc">
                      {item.present_count}/{item.countable_count} present
                      {item.excused_count > 0 ? ` · ${item.excused_count} excused` : ''}
                    </div>
                  </>
                )}
              </td>
              <td className="dept-desc">{item.marked_by_name}</td>
              <td>
                <div className="action-buttons">
                  <button
                    type="button"
                    className="table-btn view-btn"
                    onClick={() => onOpen(item)}
                    disabled={busyId === item.id}
                  >
                    Open
                  </button>
                  {!item.is_cancelled && (
                    <button
                      type="button"
                      className="table-btn warn-btn"
                      onClick={() => onCancel(item)}
                      disabled={busyId === item.id}
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    type="button"
                    className="table-btn delete-btn"
                    onClick={() => onDelete(item)}
                    disabled={busyId === item.id}
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
