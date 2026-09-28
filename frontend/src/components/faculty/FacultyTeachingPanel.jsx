import attendanceService from '../../services/attendanceService';
import timetableService from '../../services/timetableService';
import teachingAssignmentService from '../../services/teachingAssignmentService';
import useAsyncPanel from '../../hooks/useAsyncPanel';
import { formatPercent, pct } from '../charts/chartUtils';

/**
 * What a lecturer actually teaches.
 *
 * Replaces a placeholder that promised "Assigned Subjects / Teaching Schedule
 * / Classes / Attendance Statistics" as things still to come. All four have
 * existed since the timetable and attendance modules shipped.
 */
export default function FacultyTeachingPanel({ facultyId }) {
  const { data, loading, error } = useAsyncPanel(
    async () => {
      const [assignments, entries, sessions] = await Promise.all([
        teachingAssignmentService.list({ faculty_id: facultyId }),
        timetableService.list({ faculty_id: facultyId }),
        attendanceService.sessions({ faculty_id: facultyId, session_status: 'HELD' }),
      ]);
      return { assignments, entries, sessions };
    },
    [facultyId],
    { enabled: Boolean(facultyId) },
  );

  if (loading) return <p className="empty-note">Loading teaching record...</p>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return null;

  const { assignments, entries, sessions } = data;
  const sections = new Set(assignments.map((a) => a.section_id));

  const present = sessions.reduce((sum, s) => sum + (s.present_count || 0), 0);
  const countable = sessions.reduce((sum, s) => sum + (s.countable_count || 0), 0);

  return (
    <>
      <div className="profile-section-title">Teaching</div>
      <section className="mini-stats">
        <div className="mini-stat">
          <span className="mini-stat-label">Subjects</span>
          <strong className="mini-stat-value tone-blue">
            {new Set(assignments.map((a) => a.subject_id)).size}
          </strong>
        </div>
        <div className="mini-stat">
          <span className="mini-stat-label">Sections</span>
          <strong className="mini-stat-value tone-blue">{sections.size}</strong>
        </div>
        <div className="mini-stat">
          <span className="mini-stat-label">Weekly Classes</span>
          <strong className="mini-stat-value tone-blue">{entries.length}</strong>
        </div>
        <div className="mini-stat">
          <span className="mini-stat-label">Registers</span>
          <strong className="mini-stat-value tone-gray">{sessions.length}</strong>
        </div>
        <div className="mini-stat">
          <span className="mini-stat-label">Class Attendance</span>
          <strong className="mini-stat-value tone-green">
            {countable ? formatPercent(pct(present, countable), 1) : '—'}
          </strong>
        </div>
      </section>

      {assignments.length === 0 ? (
        <p className="empty-note">No subjects are assigned to this lecturer yet.</p>
      ) : (
        <div className="department-table-wrap scroll-table">
          <table className="department-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Section</th>
                <th>Scheduled</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((item) => {
                const slots = entries.filter(
                  (entry) => entry.teaching_assignment_id === item.id,
                );
                return (
                  <tr key={item.id} className={item.is_active ? '' : 'row-inactive'}>
                    <td>
                      <div className="dept-name">{item.subject_name}</div>
                      <div className="dept-desc mono">{item.subject_code}</div>
                    </td>
                    <td>{item.section_name}</td>
                    <td>
                      {slots.length ? (
                        slots.map((slot) => (
                          <div key={slot.id} className="dept-desc">
                            {slot.day_name} · {slot.slot_name}
                          </div>
                        ))
                      ) : (
                        <span className="status-badge inactive">Not scheduled</span>
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
