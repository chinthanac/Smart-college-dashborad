import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import timetableService, { DAY_NAMES, apiErrorMessage, todayIndex } from '../services/timetableService';
import MyTimetable, { TodayClasses } from '../components/timetable/MyTimetable';
import MyAttendance from '../components/attendance/MyAttendance';
import MyResults from '../components/marks/MyResults';
import attendanceService from '../services/attendanceService';

const STUDENTS_API_URL = 'http://localhost:8000/api/students';

const formatDate = (value) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
};

export default function StudentDashboard() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ phone: '', address: '' });
  const [saving, setSaving] = useState(false);
  const [myEntries, setMyEntries] = useState([]);
  const [slots, setSlots] = useState([]);
  const [loadingTimetable, setLoadingTimetable] = useState(true);
  const [attendance, setAttendance] = useState(null);
  const [loadingAttendance, setLoadingAttendance] = useState(true);
  const [attendanceError, setAttendanceError] = useState('');

  const token = localStorage.getItem('smart_college_token');

  const handleLogout = () => {
    localStorage.removeItem('smart_college_token');
    localStorage.removeItem('smart_college_user');
    navigate('/login');
    window.location.reload();
  };

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchDashboard = async () => {
      const [profileResult, timetableResult, slotsResult, attendanceResult] = await Promise.allSettled([
        axios.get(`${STUDENTS_API_URL}/me/profile`, { headers: { Authorization: `Bearer ${token}` } }),
        timetableService.mine(),
        timetableService.timeSlots(true),
        attendanceService.mine(),
      ]);

      if (profileResult.status === 'fulfilled') {
        setProfile(profileResult.value.data);
      } else {
        if (profileResult.reason?.response?.status === 401) {
          handleLogout();
          return;
        }
        setError(apiErrorMessage(profileResult.reason, 'Unable to load your profile.'));
      }

      // An empty week is normal — only a real failure is worth an error, and
      // never one that hides a profile error already on screen.
      if (timetableResult.status === 'fulfilled') {
        setMyEntries(timetableResult.value);
      } else {
        setError((current) => current || apiErrorMessage(timetableResult.reason, 'Unable to load your timetable.'));
      }

      if (slotsResult.status === 'fulfilled') {
        setSlots(slotsResult.value);
      }
      setLoadingTimetable(false);

      // Nothing marked yet is the normal opening state, so this error stays
      // inside the attendance panel rather than covering the dashboard.
      if (attendanceResult.status === 'fulfilled') {
        setAttendance(attendanceResult.value);
      } else {
        setAttendanceError(
          apiErrorMessage(attendanceResult.reason, 'Unable to load your attendance.'),
        );
      }
      setLoadingAttendance(false);
    };

    fetchDashboard();
  }, [token, navigate]);

  const openEditor = () => {
    setForm({ phone: profile.phone, address: profile.address || '' });
    setEditing(true);
    setError('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');

    try {
      const response = await axios.put(`${STUDENTS_API_URL}/me/profile`, form, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setProfile(response.data);
      setEditing(false);
      setNotice('Your details were updated.');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not update your details.');
    } finally {
      setSaving(false);
    }
  };

  if (!profile) {
    return (
      <div className="page-shell">
        <div className="dashboard-card compact">
          <p className="info-box">Loading your dashboard...</p>
          {error && <div className="error-box">{error}</div>}
        </div>
      </div>
    );
  }

  const stats = [
    { label: 'CGPA', value: '—', tone: 'blue' },
    {
      label: 'Attendance',
      value: attendance && attendance.overall_countable
        ? `${attendance.overall_percentage}%`
        : '—',
      tone: 'green',
    },
    {
      label: 'Classes Today',
      value: myEntries.filter((e) => e.day_of_week === todayIndex() && e.is_active).length,
      tone: 'orange',
    },
    { label: 'Current Semester', value: profile.semester_number ?? '—', tone: 'purple' },
  ];

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="brand-box">
          <div className="brand-mark">S</div>
          <div className="brand-text">
            <span className="brand-main">SMART COLLEGE</span>
            <span className="brand-sub">STUDENT</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-group">
            <span className="nav-group-title">Overview</span>
            <button className="nav-item active" type="button">
              <span className="nav-icon">◫</span>
              <span className="nav-label">Dashboard</span>
            </button>
          </div>

          <div className="nav-group">
            <span className="nav-group-title">Academics</span>
            {[
              { label: 'My Subjects', ready: false },
              { label: 'Timetable', ready: true },
              { label: 'Attendance', ready: true, target: 'my-attendance' },
              { label: 'My Results', ready: true, target: 'my-results' },
              { label: 'Assignments', ready: false },
              { label: 'Study Materials', ready: false },
            ].map((item) => (
              <button
                key={item.label}
                className={`nav-item ${item.ready ? '' : 'upcoming'}`}
                type="button"
                disabled={!item.ready}
                onClick={() =>
                  item.ready &&
                  document
                    .getElementById(item.target || 'my-timetable')
                    ?.scrollIntoView({ behavior: 'smooth' })
                }
              >
                <span className="nav-icon">{item.ready ? '◷' : '◌'}</span>
                <span className="nav-label">{item.label}</span>
                {!item.ready && <span className="nav-soon">soon</span>}
              </button>
            ))}
          </div>

          <div className="nav-group">
            <span className="nav-group-title">Insights</span>
            {['Performance', 'AI Assistant'].map((label) => (
              <button key={label} className="nav-item upcoming" type="button" disabled>
                <span className="nav-icon">◌</span>
                <span className="nav-label">{label}</span>
                <span className="nav-soon">soon</span>
              </button>
            ))}
          </div>

          <div className="nav-group">
            <button className="nav-item logout" type="button" onClick={handleLogout}>
              <span className="nav-icon">⏻</span>
              <span className="nav-label">Logout</span>
            </button>
          </div>
        </nav>
      </aside>

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Welcome, {profile.full_name} 👋</strong>
            <span className="page-subtitle">
              {profile.course_name} · {profile.semester_name} · {profile.section_name}
            </span>
          </div>

          <div className="topbar-right">
            <button type="button" className="secondary-btn" onClick={openEditor}>Edit My Details</button>
          </div>
        </header>

        {error && <div className="error-box dismissable" onClick={() => setError('')}>{error}</div>}
        {notice && <div className="success-box dismissable" onClick={() => setNotice('')}>{notice}</div>}

        <section className="stats-grid">
          {stats.map((item) => (
            <div key={item.label} className="stat-card">
              <div className="stat-label-row">
                <span className="stat-label">{item.label}</span>
                <div className={`stat-icon ${item.tone}`}>🎓</div>
              </div>
              <div className="stat-value">{item.value}</div>
              <div className="stat-meta">
                <span>
                  {item.label === 'Current Semester'
                    ? profile.academic_year_name
                    : item.label === 'Classes Today'
                      ? DAY_NAMES[todayIndex()]
                      : item.label === 'Attendance'
                        ? (attendance && attendance.overall_countable
                            ? `${attendance.overall_present}/${attendance.overall_countable} classes`
                            : 'nothing marked yet')
                        : 'available after the Subject module'}
                </span>
              </div>
            </div>
          ))}
        </section>

        <section className="middle-grid faculty-grid">
          <div className="panel">
            <div className="panel-header"><h3>My Details</h3></div>
            <div className="profile-grid">
              <div><span>Student ID</span><strong className="mono">{profile.student_id}</strong></div>
              <div><span>Email</span><strong>{profile.email}</strong></div>
              <div><span>Phone</span><strong>{profile.phone}</strong></div>
              <div><span>Date of Birth</span><strong>{formatDate(profile.date_of_birth)}</strong></div>
              <div><span>Department</span><strong>{profile.department_name}</strong></div>
              <div><span>Course</span><strong>{profile.course_name}</strong></div>
              <div><span>Academic Year</span><strong>{profile.academic_year_name}</strong></div>
              <div><span>Section</span><strong>{profile.section_name}</strong></div>
              <div className="span-2"><span>Address</span><strong>{profile.address || '—'}</strong></div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header"><h3>Today's Classes</h3></div>
            <TodayClasses entries={myEntries} loading={loadingTimetable} />

            <div className="panel-header" style={{ marginTop: '18px' }}><h3>AI Insight</h3></div>
            <p className="empty-note">
              Insights need attendance and marks data. They arrive after the Attendance and Marks modules.
            </p>
          </div>
        </section>

        <MyTimetable
          id="my-timetable"
          entries={myEntries}
          slots={slots}
          loading={loadingTimetable}
          showFaculty
          emptyText="Your timetable appears once your admin schedules classes for your section."
        />

        <MyAttendance
          id="my-attendance"
          summary={attendance}
          loading={loadingAttendance}
          error={attendanceError}
        />

        <MyResults />
      </main>

      {editing && (
        <div className="modal-backdrop" onClick={() => setEditing(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Edit My Details</h3>
            <p className="modal-hint">
              Your student ID, department, course, semester, and section are managed by the Admin.
            </p>

            <form className="department-form" onSubmit={handleSubmit}>
              <label>
                Phone
                <input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </label>

              <label>
                Address
                <textarea rows="3" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
              </label>

              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={() => setEditing(false)}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={saving}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
