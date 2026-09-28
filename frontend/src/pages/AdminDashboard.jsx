import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminSidebar, { clearAuthState } from '../components/AdminSidebar';
import BarList from '../components/charts/BarList';
import ChartEmpty from '../components/charts/ChartEmpty';
import DonutChart from '../components/charts/DonutChart';
import GaugeRing from '../components/charts/GaugeRing';
import SeriesChart from '../components/charts/SeriesChart';
import { formatCount, formatPercent } from '../components/charts/chartUtils';
import statsService, {
  apiErrorMessage,
  formatDateValue,
  formatMoment,
} from '../services/statsService';
import { adminRoutePaths } from '../App';

const AUTH_API_URL = 'http://localhost:8000/api/auth';

/**
 * Filtered against the real route table below, so a quick action pointing at
 * a page that does not exist disappears instead of doing what the previous
 * two did: fall through the router's catch-all and log the admin out.
 */
const RAW_ACTIONS = [
  { label: 'Add Department', route: '/admin/departments', openCreate: true },
  { label: 'Add Faculty', route: '/admin/faculty' },
  { label: 'Add Student', route: '/admin/students' },
  { label: 'Add Subject', route: '/admin/subjects' },
  { label: 'Assign Teaching', route: '/admin/teaching-assignments' },
  { label: 'Build Timetable', route: '/admin/timetable' },
  { label: 'New Assessment', route: '/admin/assessments' },
  { label: 'View Results', route: '/admin/results' },
];

const ROLE_LABEL = {
  ADMIN: 'Administrator',
  FACULTY: 'Faculty',
  STUDENT: 'Student',
};

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('smart_college_token');
    if (!token) {
      navigate('/login');
      return;
    }

    const load = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const [me, dashboard] = await Promise.all([
          axios.get(`${AUTH_API_URL}/me`, { headers }),
          statsService.dashboard(),
        ]);
        setUser(me.data);
        setStats(dashboard);
        setError('');
      } catch (err) {
        // Only a rejected token means the session is gone; a failed data
        // request should not throw the Admin back to the login screen.
        if (err?.response?.status === 401 || err?.response?.status === 403) {
          clearAuthState();
          navigate('/login');
          return;
        }
        setError(apiErrorMessage(err, 'Some dashboard data could not be loaded.'));
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [navigate]);

  const handleLogout = () => {
    clearAuthState();
    navigate('/login');
    window.location.reload();
  };

  const quickActions = useMemo(
    () => RAW_ACTIONS.filter((action) => adminRoutePaths.includes(action.route)),
    [],
  );

  const counts = stats?.counts;
  const attendance = stats?.attendance;
  const series = stats?.attendance_series;
  const today = stats?.today;
  const assessments = stats?.assessments;

  const statCards = counts
    ? [
        { label: 'Students', value: counts.students, icon: '◇', route: '/admin/students',
          meta: `${formatCount(counts.active_students)} active` },
        { label: 'Faculty', value: counts.faculty, icon: '◈', route: '/admin/faculty',
          meta: `across ${counts.departments} departments` },
        { label: 'Departments', value: counts.departments, icon: '▣', route: '/admin/departments',
          meta: `${counts.courses} courses` },
        { label: 'Subjects', value: counts.subjects, icon: '◍', route: '/admin/subjects',
          meta: `${counts.teaching_assignments} assignments` },
        { label: 'Scheduled Classes', value: counts.timetable_entries, icon: '◷',
          route: '/admin/timetable', meta: `${counts.sections} sections` },
      ]
    : [];

  if (loading) {
    return (
      <div className="admin-layout">
        <AdminSidebar />
        <main className="content-panel">
          <header className="topbar">
            <div className="welcome-text"><strong>Dashboard</strong></div>
          </header>
          <section className="stats-grid">
            {[0, 1, 2, 3, 4].map((key) => (
              <div key={key} className="stat-card is-skeleton" aria-hidden="true" />
            ))}
          </section>
          <div className="dash-grid-2">
            <div className="panel is-skeleton" aria-hidden="true" />
            <div className="panel is-skeleton" aria-hidden="true" />
          </div>
          <p className="visually-hidden" role="status">Loading dashboard</p>
        </main>
      </div>
    );
  }

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel">
        <header className="topbar">
          <div className="topbar-left">
            <div className="welcome-text">
              <strong>Welcome back, {user?.name || 'Admin'}</strong>
              {stats && (
                <span className="page-subtitle">
                  Figures as of {formatMoment(stats.generated_at)}
                </span>
              )}
            </div>
          </div>

          <div className="topbar-right">
            <div className="profile-box">
              <div className="avatar">{(user?.name || 'A').charAt(0).toUpperCase()}</div>
              <div>
                <div className="profile-name">{user?.name || '—'}</div>
                <div className="profile-role">{ROLE_LABEL[user?.role] || user?.role}</div>
              </div>
            </div>
            <button className="secondary-btn" onClick={handleLogout}>Logout</button>
          </div>
        </header>

        {error && (
          <div className="error-box dismissable" onClick={() => setError('')} role="alert">
            {error}
          </div>
        )}

        <section className="stats-grid">
          {statCards.map((item) => (
            <button
              key={item.label}
              type="button"
              className="stat-card"
              onClick={() => navigate(item.route)}
            >
              <div className="stat-label-row">
                <span className="stat-label">{item.label}</span>
                <div className="stat-icon blue" aria-hidden="true">{item.icon}</div>
              </div>
              <div className="stat-value">{formatCount(item.value)}</div>
              <div className="stat-meta"><span>{item.meta}</span></div>
            </button>
          ))}
        </section>

        {stats?.unscheduled_assignments > 0 && (
          <section className="panel setup-health">
            <span>
              <strong>{stats.unscheduled_assignments}</strong> teaching assignment
              {stats.unscheduled_assignments === 1 ? ' has' : 's have'} no class on the timetable.
            </span>
            <Link to="/admin/timetable" className="mini-btn">Build timetable</Link>
          </section>
        )}

        <div className="dash-grid-2">
          <section className="panel">
            <div className="panel-header">
              <h3>College Attendance</h3>
              {attendance?.has_data && (
                <span className="panel-count">
                  {formatDateValue(attendance.from_date)} – {formatDateValue(attendance.to_date)}
                </span>
              )}
            </div>

            {attendance?.has_data ? (
              <>
                <GaugeRing
                  value={attendance.attendance_percentage}
                  label="Attended"
                  caption={`${formatCount(attendance.present_count)} of ${formatCount(
                    attendance.countable_count,
                  )} marked places attended`}
                />
                <section className="mini-stats">
                  <div className="mini-stat">
                    <span className="mini-stat-label">Registers</span>
                    <strong className="mini-stat-value tone-blue">
                      {formatCount(attendance.held_sessions)}
                    </strong>
                  </div>
                  <div className="mini-stat">
                    <span className="mini-stat-label">Absent</span>
                    <strong className="mini-stat-value tone-red">
                      {formatCount(attendance.absent_count)}
                    </strong>
                  </div>
                  <div className="mini-stat">
                    <span className="mini-stat-label">Excused</span>
                    <strong className="mini-stat-value tone-gray">
                      {formatCount(attendance.excused_count)}
                    </strong>
                  </div>
                  <div className="mini-stat">
                    <span className="mini-stat-label">Cancelled</span>
                    <strong className="mini-stat-value tone-gray">
                      {formatCount(attendance.cancelled_sessions)}
                    </strong>
                  </div>
                </section>
              </>
            ) : (
              <ChartEmpty
                title="No registers have been marked yet"
                hint="Attendance appears here once lecturers start taking the register."
                action={<Link to="/admin/attendance" className="mini-btn">Open attendance</Link>}
              />
            )}
          </section>

          <section className="panel">
            <div className="panel-header">
              <h3>Attendance by Month</h3>
              {series?.anchor_label && (
                <span className="panel-count">12 months to {series.anchor_label}</span>
              )}
            </div>

            {/* An old anchor is stated plainly rather than drawn as an empty
                chart — "no recent data" and "nobody attended" look identical
                otherwise. */}
            {series?.has_data && !series.is_current_period && (
              <p className="chart-note">Latest data is from {series.anchor_label}.</p>
            )}

            <SeriesChart
              points={series?.months || []}
              emptyTitle="No attendance has been marked yet"
              emptyHint="The trend appears once registers exist."
            />
          </section>
        </div>

        <div className="dash-grid-2">
          <section className="panel">
            <div className="panel-header">
              <h3>Students by Department</h3>
              <Link to="/admin/students" className="mini-btn">All students</Link>
            </div>
            <DonutChart
              data={(stats?.students_by_department || []).map((row) => ({
                id: row.department_id,
                label: row.department_code || row.department_name,
                value: row.student_count,
              }))}
              centerValue={counts?.students}
              centerLabel="Students"
              emptyTitle="No students enrolled yet"
              emptyHint="Add students and they will appear here by department."
            />
          </section>

          <section className="panel">
            <div className="panel-header">
              <h3>Section Capacity</h3>
              <span className="panel-count">{stats?.section_fill?.length || 0} fullest</span>
            </div>
            <BarList
              rows={(stats?.section_fill || []).map((row) => ({
                id: row.section_id,
                label: `${row.section_name} (${row.section_code})`,
                caption: `${row.enrolled}/${row.capacity}`,
                percentage: row.fill_percentage,
                tone: row.over_capacity ? 'danger' : row.fill_percentage > 85 ? 'warn' : 'ok',
                hint: row.semester_name,
              }))}
              emptyTitle="No sections yet"
              emptyHint="Sections appear here with their enrolment."
            />
          </section>
        </div>

        <div className="dash-grid-2">
          <section className="panel">
            <div className="panel-header">
              <h3>Grade Distribution</h3>
              <span className="panel-count">
                {assessments?.has_data
                  ? `${formatCount(assessments.graded_results)} graded`
                  : 'No results yet'}
              </span>
            </div>
            {assessments?.has_data ? (
              <>
                <BarList
                  rows={(assessments.distribution || [])
                    .filter((band) => band.student_count > 0)
                    .map((band) => ({
                      id: band.grade_letter,
                      label: `${band.grade_letter} · ${band.grade_point} points`,
                      caption: `${band.student_count} of ${assessments.graded_results}`,
                      percentage: band.percentage,
                      tone:
                        band.grade_letter === 'F'
                          ? 'danger'
                          : band.grade_point <= 5
                            ? 'warn'
                            : 'ok',
                    }))}
                  emptyTitle="No grades yet"
                />
                <p className="panel-foot">
                  {formatPercent(assessments.pass_percentage)} passing ·{' '}
                  {formatCount(assessments.fail_count)} failing
                </p>
              </>
            ) : (
              <ChartEmpty
                title="Nothing published yet"
                hint={
                  assessments?.draft_assessments
                    ? `${formatCount(assessments.draft_assessments)} assessment(s) are still drafts. A draft reaches nobody.`
                    : 'Grades appear once an assessment is published with a complete mark sheet.'
                }
              />
            )}
          </section>

          <section className="panel">
            <div className="panel-header">
              <h3>Subjects Needing Attention</h3>
              <span className="panel-count">
                {assessments?.incomplete_sheets
                  ? `${formatCount(assessments.incomplete_sheets)} sheet(s) incomplete`
                  : 'All sheets complete'}
              </span>
            </div>
            <BarList
              rows={(assessments?.weakest_subjects || []).map((row) => ({
                id: `${row.section_id}-${row.subject_id}`,
                label: `${row.subject_code} · ${row.section_name}`,
                caption: `${formatPercent(row.pass_percentage)} pass`,
                percentage: row.pass_percentage,
                tone: row.pass_percentage < 50 ? 'danger' : row.pass_percentage < 75 ? 'warn' : 'ok',
                hint: `${row.graded_students} graded · avg ${row.average_percent}% · ${row.faculty_name || 'Unassigned'}`,
              }))}
              emptyTitle="Nothing to flag"
              emptyHint="Subjects appear here once their results are published, weakest pass rate first."
            />
          </section>
        </div>

        <div className="dash-grid-2">
          <section className="panel">
            <div className="panel-header">
              <h3>Today</h3>
              <span className="panel-count">{today?.day_name}</span>
            </div>

            {today?.scheduled_classes ? (
              <section className="mini-stats">
                <div className="mini-stat">
                  <span className="mini-stat-label">Scheduled</span>
                  <strong className="mini-stat-value tone-blue">{today.scheduled_classes}</strong>
                </div>
                <div className="mini-stat">
                  <span className="mini-stat-label">Marked</span>
                  <strong className="mini-stat-value tone-green">{today.marked_sessions}</strong>
                </div>
                <div className="mini-stat">
                  <span className="mini-stat-label">Cancelled</span>
                  <strong className="mini-stat-value tone-gray">{today.cancelled_sessions}</strong>
                </div>
                <div className="mini-stat">
                  <span className="mini-stat-label">Still to mark</span>
                  <strong
                    className={`mini-stat-value ${
                      today.unmarked_classes ? 'tone-red' : 'tone-green'
                    }`}
                  >
                    {today.unmarked_classes}
                  </strong>
                </div>
              </section>
            ) : (
              <p className="empty-note">No classes are scheduled on {today?.day_name}.</p>
            )}

            {today?.unmarked_classes > 0 && (
              <Link to="/admin/attendance" className="mini-btn">Review attendance</Link>
            )}
          </section>

          <section className="panel">
            <div className="panel-header">
              <h3>Recent Registers</h3>
              <Link to="/admin/attendance" className="mini-btn">All registers</Link>
            </div>

            {stats?.recent_registers?.length ? (
              <div className="department-table-wrap scroll-table">
                <table className="department-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Class</th>
                      <th>Attendance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.recent_registers.map((row) => (
                      <tr key={row.session_id}>
                        <td>
                          <div className="dept-name">{formatDateValue(row.class_date)}</div>
                          <div className="dept-desc">{row.day_name}</div>
                        </td>
                        <td>
                          <div className="dept-name">{row.subject_code}</div>
                          <div className="dept-desc">
                            {row.section_name} · {row.faculty_name}
                          </div>
                        </td>
                        <td>
                          {row.session_status === 'CANCELLED' ? (
                            <span className="status-badge inactive">Cancelled</span>
                          ) : (
                            <>
                              <strong>{formatPercent(row.attendance_percentage, 0)}</strong>
                              <div className="dept-desc">
                                {row.present_count}/{row.countable_count}
                              </div>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <ChartEmpty title="No registers yet" />
            )}
          </section>
        </div>

        <section className="panel">
          <div className="panel-header">
            <h3>Quick Actions</h3>
          </div>
          <div className="quick-grid">
            {quickActions.map((action, index) => (
              <button
                key={action.label}
                type="button"
                className={`quick-card color-${(index % 6) + 1}`}
                onClick={() =>
                  navigate(
                    action.route,
                    action.openCreate ? { state: { openCreate: true } } : undefined,
                  )
                }
              >
                <span className="quick-icon" aria-hidden="true">✦</span>
                <span>{action.label}</span>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
