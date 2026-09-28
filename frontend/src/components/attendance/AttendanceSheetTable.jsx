import { ATTENDANCE_STATUSES, STATUS_LABEL } from '../../services/attendanceService';

// Present and Late read as "was here", so they carry the positive colours.
const STATUS_BTN = {
  PRESENT: 'success-btn',
  LATE: 'warn-btn',
  ABSENT: 'delete-btn',
  EXCUSED: 'edit-btn',
};

/**
 * The roster. One row per student, four mutually exclusive statuses.
 *
 * A row with no `id` has never been saved — a student admitted after the
 * sheet was marked. It is shown exactly like any other so they cannot be
 * quietly missed.
 */
export default function AttendanceSheetTable({ records, disabled, onChange, onMarkAll }) {
  if (!records.length) {
    return <p className="empty-note">No students to mark.</p>;
  }

  return (
    <>
      <div className="action-buttons attendance-bulk">
        <button
          type="button"
          className="table-btn success-btn"
          onClick={() => onMarkAll('PRESENT')}
          disabled={disabled}
        >
          Mark all present
        </button>
        <button
          type="button"
          className="table-btn delete-btn"
          onClick={() => onMarkAll('ABSENT')}
          disabled={disabled}
        >
          Mark all absent
        </button>
      </div>

      <div className="department-table-wrap scroll-table">
        <table className="department-table">
          <thead>
            <tr>
              <th>Roll No</th>
              <th>Student</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.student_id}>
                <td className="mono">{record.student_code}</td>
                <td>
                  <div className="dept-name">{record.student_name}</div>
                  {record.moved_section && (
                    <span className="type-chip type-cross-dept" title={`Now in ${record.student_section_name}`}>
                      TRANSFERRED
                    </span>
                  )}
                  {record.student_status && record.student_status !== 'ACTIVE' && (
                    <span className="status-badge inactive">{record.student_status}</span>
                  )}
                </td>
                <td>
                  <div className="attendance-status-group">
                    {ATTENDANCE_STATUSES.map((status) => (
                      <button
                        key={status}
                        type="button"
                        className={`table-btn ${STATUS_BTN[status]} ${
                          record.status === status ? 'is-selected' : ''
                        }`}
                        onClick={() => onChange(record.student_id, status)}
                        disabled={disabled}
                      >
                        {STATUS_LABEL[status]}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
