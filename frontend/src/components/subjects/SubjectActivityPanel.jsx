import attendanceService from '../../services/attendanceService';
import teachingAssignmentService from '../../services/teachingAssignmentService';
import useAsyncPanel from '../../hooks/useAsyncPanel';
import { formatPercent, pct } from '../charts/chartUtils';

/** Who teaches this subject, to whom, and how well attended it is. */
export default function SubjectActivityPanel({ subjectId }) {
  const { data, loading, error } = useAsyncPanel(
    async () => {
      const [assignments, sessions] = await Promise.all([
        teachingAssignmentService.list({ subject_id: subjectId }),
        attendanceService.sessions({ subject_id: subjectId, session_status: 'HELD' }),
      ]);
      return { assignments, sessions };
    },
    [subjectId],
    { enabled: Boolean(subjectId) },
  );

  if (loading) return <p className="empty-note">Loading activity...</p>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return null;

  const { assignments, sessions } = data;
  const present = sessions.reduce((sum, s) => sum + (s.present_count || 0), 0);
  const countable = sessions.reduce((sum, s) => sum + (s.countable_count || 0), 0);

  return (
    <>
      <div className="profile-section-title">Teaching &amp; Attendance</div>

      <section className="mini-stats">
        <div className="mini-stat">
          <span className="mini-stat-label">Sections</span>
          <strong className="mini-stat-value tone-blue">{assignments.length}</strong>
        </div>
        <div className="mini-stat">
          <span className="mini-stat-label">Registers</span>
          <strong className="mini-stat-value tone-gray">{sessions.length}</strong>
        </div>
        <div className="mini-stat">
          <span className="mini-stat-label">Attendance</span>
          <strong className="mini-stat-value tone-green">
            {countable ? formatPercent(pct(present, countable), 1) : '—'}
          </strong>
        </div>
      </section>

      {assignments.length === 0 ? (
        <p className="empty-note">
          This subject is not assigned to any section yet.
        </p>
      ) : (
        <div className="department-table-wrap scroll-table">
          <table className="department-table">
            <thead>
              <tr>
                <th>Section</th>
                <th>Faculty</th>
                <th>Registers</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((item) => {
                const mine = sessions.filter((s) => s.section_id === item.section_id);
                const p = mine.reduce((sum, s) => sum + (s.present_count || 0), 0);
                const c = mine.reduce((sum, s) => sum + (s.countable_count || 0), 0);
                return (
                  <tr key={item.id} className={item.is_active ? '' : 'row-inactive'}>
                    <td>{item.section_name}</td>
                    <td>{item.faculty_name}</td>
                    <td>
                      {mine.length}
                      {c > 0 && (
                        <div className="dept-desc">{formatPercent(pct(p, c), 1)} attended</div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
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
