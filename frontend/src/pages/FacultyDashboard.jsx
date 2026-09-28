import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import teachingAssignmentService from '../services/teachingAssignmentService';
import timetableService, { DAY_NAMES, apiErrorMessage, todayIndex } from '../services/timetableService';
import MyTimetable from '../components/timetable/MyTimetable';
import attendanceService, { toDateValue } from '../services/attendanceService';

const FACULTY_API_URL = 'http://localhost:8000/api/faculty';

const formatDate = (value) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
};

export default function FacultyDashboard() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [loadingAssignments, setLoadingAssignments] = useState(true);
  const [myEntries, setMyEntries] = useState([]);
  const [slots, setSlots] = useState([]);
  const [loadingTimetable, setLoadingTimetable] = useState(true);
  const [toMark, setToMark] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ first_name: '', last_name: '', phone: '', qualification: '' });
  const [saving, setSaving] = useState(false);

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

    // allSettled so a failing assignments call can never blank the profile
    const fetchDashboard = async () => {
      const [profileResult, assignmentsResult, timetableResult, slotsResult, classesResult] = await Promise.allSettled([
        axios.get(`${FACULTY_API_URL}/me/profile`, { headers: { Authorization: `Bearer ${token}` } }),
        teachingAssignmentService.mine(),
        timetableService.mine(),
        timetableService.timeSlots(true),
        attendanceService.myClasses(toDateValue()),
      ]);

      if (profileResult.status === 'fulfilled') {
        setProfile(profileResult.value.data);
      } else {
        if (profileResult.reason?.response?.status === 401) {
          handleLogout();
          return;
        }
        setError(profileResult.reason?.response?.data?.detail || 'Unable to load your profile.');
      }

      if (assignmentsResult.status === 'fulfilled') {
        setAssignments(assignmentsResult.value);
      } else {
        setError(
          assignmentsResult.reason?.response?.data?.detail || 'Unable to load your teaching assignments.',
        );
      }
      setLoadingAssignments(false);

      // A failing timetable must not stomp a profile or assignment error that
      // already explains more.
      if (timetableResult.status === 'fulfilled') {
        setMyEntries(timetableResult.value);
      } else {
        setError((current) => current || apiErrorMessage(timetableResult.reason, 'Unable to load your timetable.'));
      }

      if (slotsResult.status === 'fulfilled') {
        setSlots(slotsResult.value);
      }

      // An empty day is normal, so a failure here never becomes an error.
      if (classesResult.status === 'fulfilled') {
        setToMark(classesResult.value.filter((c) => c.status === 'UNMARKED').length);
      }
      setLoadingTimetable(false);
    };

    fetchDashboard();
  }, [token, navigate]);

  const stats = useMemo(
    () => [
      {
        label: 'My Subjects',
        value: new Set(assignments.map((a) => a.subject_id)).size,
        tone: 'blue',
        meta: 'assigned across your sections',
      },
      {
        label: 'My Sections',
        value: new Set(assignments.map((a) => a.section_id)).size,
        tone: 'purple',
        meta: 'sections you teach',
      },
      {
        label: "Today's Classes",
        value: myEntries.filter((e) => e.day_of_week === todayIndex() && e.is_active).length,
        tone: 'green',
        meta: `scheduled on ${DAY_NAMES[todayIndex()]}`,
      },
      {
        label: 'To Mark Today',
        value: toMark,
        tone: 'orange',
        meta: 'registers not taken yet',
      },
    ],
    [assignments, myEntries, toMark],
  );

  const openEditor = () => {
    setForm({
      first_name: profile.first_name,
      last_name: profile.last_name,
      phone: profile.phone,
      qualification: profile.qualification,
    });
    setEditing(true);
    setError('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');

    try {
      const response = await axios.put(`${FACULTY_API_URL}/me/profile`, form, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setProfile(response.data);
      setEditing(false);
      setNotice('Your profile was updated.');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not update your profile.');
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

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="brand-box">
          <div className="brand-mark">S</div>
          <div className="brand-text">
            <span className="brand-main">SMART COLLEGE</span>
            <span className="brand-sub">FACULTY</span>
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
            <span className="nav-group-title">Teaching</span>
            {[
              { label: 'My Subjects', ready: true, target: 'my-subjects' },
              { label: 'My Timetable', ready: true, target: 'my-timetable' },
              { label: 'Attendance', ready: true, route: '/faculty/attendance' },
              { label: 'Marks', ready: true, route: '/faculty/marks' },
              { label: 'Assignments', ready: false },
              { label: 'Study Materials', ready: false },
            ].map((item) => (
              <button
                key={item.label}
                className={`nav-item ${item.ready ? '' : 'upcoming'}`}
                type="button"
                disabled={!item.ready}
                onClick={() => {
                  if (!item.ready) return;
                  if (item.route) navigate(item.route);
                  else
                    document
                      .getElementById(item.target || 'my-timetable')
                      ?.scrollIntoView({ behavior: 'smooth' });
                }}
              >
                <span className="nav-icon">{item.ready ? '◷' : '◌'}</span>
                <span className="nav-label">{item.label}</span>
                {!item.ready && <span className="nav-soon">soon</span>}
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
            <strong>Welcome, {profile.full_name}</strong>
            <span className="page-subtitle">
              {profile.designation} · {profile.department_name}
            </span>
          </div>

          <div className="topbar-right">
            <button type="button" className="secondary-btn" onClick={openEditor}>Edit My Profile</button>
          </div>
        </header>

        {error && <div className="error-box dismissable" onClick={() => setError('')}>{error}</div>}
        {notice && <div className="success-box dismissable" onClick={() => setNotice('')}>{notice}</div>}

        <section className="stats-grid">
          {stats.map((item) => (
            <div key={item.label} className="stat-card">
              <div className="stat-label-row">
                <span className="stat-label">{item.label}</span>
                <div className={`stat-icon ${item.tone}`}>📘</div>
              </div>
              <div className="stat-value">{item.value}</div>
              <div className="stat-meta">
                <span>{item.meta}</span>
              </div>
            </div>
          ))}
        </section>

        <section className="middle-grid faculty-grid">
          <div className="panel">
            <div className="panel-header">
              <h3>My Profile</h3>
            </div>
            <div className="profile-grid">
              <div><span>Faculty ID</span><strong className="mono">{profile.faculty_id}</strong></div>
              <div><span>Email</span><strong>{profile.email}</strong></div>
              <div><span>Phone</span><strong>{profile.phone}</strong></div>
              <div><span>Department</span><strong>{profile.department_name}</strong></div>
              <div><span>Designation</span><strong>{profile.designation}</strong></div>
              <div><span>Qualification</span><strong>{profile.qualification}</strong></div>
              <div><span>Employee Type</span><strong>{profile.employee_type}</strong></div>
              <div><span>Joining Date</span><strong>{formatDate(profile.joining_date)}</strong></div>
            </div>
          </div>

          <div className="panel" id="my-subjects">
            <div className="panel-header">
              <h3>My Subjects</h3>
              {!loadingAssignments && assignments.length > 0 && (
                <span className="panel-count">
                  {assignments.length} assignment{assignments.length === 1 ? '' : 's'}
                </span>
              )}
            </div>

            {loadingAssignments ? (
              <p className="empty-note">Loading your subjects...</p>
            ) : assignments.length === 0 ? (
              <p className="empty-note">
                No subjects have been assigned to you yet. Your admin assigns subjects section by section.
              </p>
            ) : (
              <div className="department-table-wrap scroll-table">
                <table className="department-table">
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th>Section</th>
                      <th>Semester</th>
                      <th>Credits</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assignments.map((item) => (
                      <tr key={item.id} className={item.is_active ? '' : 'row-inactive'}>
                        <td>
                          <div className="dept-name">{item.subject_name}</div>
                          <div className="dept-desc mono">{item.subject_code}</div>
                        </td>
                        <td>
                          <div>{item.section_name}</div>
                          <div className="dept-desc">{item.section_room_number}</div>
                        </td>
                        <td>{item.semester_name}</td>
                        <td>{item.subject_credits}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        <MyTimetable
          id="my-timetable"
          entries={myEntries}
          slots={slots}
          loading={loadingTimetable}
          showSection
          emptyText="Nothing is scheduled for you yet. Your admin places classes on the timetable."
        />
      </main>

      {editing && (
        <div className="modal-backdrop" onClick={() => setEditing(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Edit My Profile</h3>
            <p className="modal-hint">
              Your faculty ID, department, and designation are managed by the Admin.
            </p>

            <form className="department-form" onSubmit={handleSubmit}>
              <label>
                First Name
                <input
                  type="text"
                  value={form.first_name}
                  onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                />
              </label>

              <label>
                Last Name
                <input
                  type="text"
                  value={form.last_name}
                  onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                />
              </label>

              <label>
                Phone
                <input
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </label>

              <label>
                Qualification
                <input
                  type="text"
                  value={form.qualification}
                  onChange={(e) => setForm({ ...form, qualification: e.target.value })}
                />
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
