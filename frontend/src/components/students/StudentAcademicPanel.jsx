import attendanceService, {
  STANDING_CLASS,
  STANDING_LABEL,
} from '../../services/attendanceService';
import useAsyncPanel from '../../hooks/useAsyncPanel';
import { clamp, formatPercent } from '../charts/chartUtils';

/**
 * A student's attendance, per subject.
 *
 * Replaces a placeholder that listed "Attendance" as still to come — the
 * report endpoint behind this has existed since the attendance module.
 */
export default function StudentAcademicPanel({ studentId }) {
  const { data, loading, error } = useAsyncPanel(
    () => attendanceService.studentReport({ student_id: studentId }),
    [studentId],
    { enabled: Boolean(studentId) },
  );

  if (loading) return <p className="empty-note">Loading attendance...</p>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return null;

  const hasData = data.overall_countable > 0;

  return (
    <>
      <div className="profile-section-title">Attendance</div>

      {!hasData ? (
        <p className="empty-note">
          Nothing has been marked for this student yet.
        </p>
      ) : (
        <>
          <section className="mini-stats">
            <div className="mini-stat">
              <span className="mini-stat-label">Overall</span>
              <strong
                className={`mini-stat-value ${
                  data.overall_percentage < data.threshold ? 'tone-red' : 'tone-green'
                }`}
              >
                {formatPercent(data.overall_percentage, 1)}
              </strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Attended</span>
              <strong className="mini-stat-value tone-blue">
                {data.overall_present}/{data.overall_countable}
              </strong>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Standing</span>
              <strong className="mini-stat-value tone-gray">
                {STANDING_LABEL[data.status]}
              </strong>
            </div>
          </section>

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
                {data.subjects.map((item) => (
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
                    <td className="attendance-percent-cell">
                      <div className="coverage-bar">
                        <div
                          className="coverage-bar-fill"
                          style={{
                            width: `${clamp(item.attendance_percentage, 0, 100)}%`,
                            background:
                              item.attendance_percentage < data.threshold
                                ? 'var(--accent-red)'
                                : 'var(--accent-green-bright)',
                          }}
                        />
                      </div>
                      <strong>{formatPercent(item.attendance_percentage, 1)}</strong>{' '}
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
