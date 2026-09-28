import attendanceService, {
  STANDING_CLASS,
  STANDING_LABEL,
} from '../../services/attendanceService';
import useAsyncPanel from '../../hooks/useAsyncPanel';
import { clamp, formatPercent } from '../charts/chartUtils';

/**
 * Attendance for exactly this subject and this section.
 *
 * This panel replaces the most obsolete claim in the codebase: a placeholder
 * promising "Attendance for this subject and section", which is precisely
 * what report/section has returned since the attendance module shipped.
 */
export default function AssignmentAttendancePanel({ assignment }) {
  const { data, loading, error } = useAsyncPanel(
    () =>
      attendanceService.sectionReport({
        section_id: assignment.section_id,
        teaching_assignment_id: assignment.id,
      }),
    [assignment.id, assignment.section_id],
    { enabled: Boolean(assignment.section_id) },
  );

  if (loading) return <p className="empty-note">Loading attendance...</p>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return null;

  return (
    <>
      <div className="profile-section-title">Attendance</div>

      {!data.held_sessions ? (
        <p className="empty-note">
          No registers have been marked for this class yet.
        </p>
      ) : (
        <>
          <section className="mini-stats">
            <div className="mini-stat">
              <span className="mini-stat-label">Classes Held</span>
              <strong className="mini-stat-value tone-blue">{data.held_sessions}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Cancelled</span>
              <strong className="mini-stat-value tone-gray">{data.cancelled_sessions}</strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Class Average</span>
              <strong className="mini-stat-value tone-green">
                {formatPercent(data.section_percentage, 1)}
              </strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Below {data.threshold}%</span>
              <strong className="mini-stat-value tone-red">{data.defaulter_count}</strong>
            </div>
          </section>

          <div className="department-table-wrap scroll-table">
            <table className="department-table">
              <thead>
                <tr>
                  <th>Roll No</th>
                  <th>Student</th>
                  <th>Attendance</th>
                </tr>
              </thead>
              <tbody>
                {data.students.map((row) => (
                  <tr key={row.student_id}>
                    <td className="mono">{row.student_code}</td>
                    <td>{row.student_name}</td>
                    <td className="attendance-percent-cell">
                      <div className="coverage-bar">
                        <div
                          className="coverage-bar-fill"
                          style={{
                            width: `${clamp(row.attendance_percentage, 0, 100)}%`,
                            background:
                              row.attendance_percentage < data.threshold
                                ? 'var(--accent-red)'
                                : 'var(--accent-green-bright)',
                          }}
                        />
                      </div>
                      <strong>{formatPercent(row.attendance_percentage, 1)}</strong>{' '}
                      <span className={`coverage-status ${STANDING_CLASS[row.status]}`}>
                        {STANDING_LABEL[row.status]}
                      </span>
                      <div className="dept-desc">
                        {row.present_count}/{row.countable_sessions} attended
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="pending-panel">
        <strong>Coming with the next modules</strong>
        <ul>
          <li>Marks and assessments</li>
          <li>Assignments &amp; study materials</li>
        </ul>
      </div>
    </>
  );
}
