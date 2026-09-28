import {
  STANDING_CLASS,
  STANDING_LABEL,
} from '../../services/attendanceService';

/**
 * A student's own record, read-only.
 *
 * Built like MyTimetable: the component owns its panel so a dashboard only
 * has to drop it in.
 */
export default function MyAttendance({ id, summary, loading, error }) {
  const subjects = summary?.subjects || [];
  const percent = summary?.overall_percentage ?? 0;

  return (
    <section className="panel" id={id}>
      <div className="panel-header">
        <h3>My Attendance</h3>
        {summary && summary.overall_countable > 0 && (
          <span className="panel-count">
            {summary.overall_present}/{summary.overall_countable} classes
          </span>
        )}
      </div>

      {loading && <p className="empty-note">Loading your attendance...</p>}
      {!loading && error && <div className="error-box">{error}</div>}

      {!loading && !error && summary && summary.overall_countable === 0 && (
        <p className="empty-note">
          Nothing has been marked yet. Your attendance appears once your lecturers start
          taking the register.
        </p>
      )}

      {!loading && !error && summary && summary.overall_countable > 0 && (
        <>
          <div className="coverage-bar">
            <div
              className="coverage-bar-fill"
              style={{
                width: `${Math.min(100, percent)}%`,
                background: percent < summary.threshold ? '#dc2626' : '#22c55e',
              }}
            />
          </div>
          <p className="modal-hint inline-hint">
            Overall <strong>{percent}%</strong> — {summary.threshold}% is the minimum.{' '}
            <span className={`coverage-status ${STANDING_CLASS[summary.status]}`}>
              {STANDING_LABEL[summary.status]}
            </span>
          </p>

          <div className="department-table-wrap scroll-table">
            <table className="department-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Attended</th>
                  <th>Percentage</th>
                </tr>
              </thead>
              <tbody>
                {subjects.map((item) => (
                  <tr key={item.subject_id}>
                    <td>
                      <div className="dept-name">{item.subject_name}</div>
                      <div className="dept-desc mono">{item.subject_code}</div>
                      <div className="dept-desc">{item.faculty_name}</div>
                    </td>
                    <td>
                      {item.present_count}/{item.countable_sessions}
                      {item.excused_count > 0 && (
                        <div className="dept-desc">{item.excused_count} excused</div>
                      )}
                    </td>
                    <td>
                      <strong>{item.attendance_percentage}%</strong>{' '}
                      <span className={`coverage-status ${STANDING_CLASS[item.status]}`}>
                        {STANDING_LABEL[item.status]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
