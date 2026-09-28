import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const navGroups = [
  {
    title: 'Overview',
    items: [{ label: 'Dashboard', route: '/admin/dashboard', icon: '◫', ready: true }],
  },
  {
    title: 'Academic Structure',
    items: [
      { label: 'Departments', route: '/admin/departments', icon: '▣', ready: true },
      { label: 'Courses', route: '/admin/courses', icon: '▤', ready: true },
      { label: 'Academic Years', route: '/admin/academic-years', icon: '▦', ready: true },
      { label: 'Semesters', route: '/admin/semesters', icon: '▧', ready: true },
      { label: 'Sections', route: '/admin/sections', icon: '▨', ready: true },
    ],
  },
  {
    title: 'People',
    items: [
      { label: 'Faculty', route: '/admin/faculty', icon: '◈', ready: true },
      { label: 'Students', route: '/admin/students', icon: '◇', ready: true },
    ],
  },
  {
    title: 'Teaching',
    items: [
      { label: 'Subjects', route: '/admin/subjects', icon: '◍', ready: true },
      { label: 'Teaching Assignments', route: '/admin/teaching-assignments', icon: '◎', ready: true },
      { label: 'Timetable', route: '/admin/timetable', icon: '◷', ready: true },
      { label: 'Attendance', route: '/admin/attendance', icon: '◑', ready: true },
      { label: 'Assessments', route: '/admin/assessments', icon: '◍', ready: true },
      { label: 'Results', route: '/admin/results', icon: '◈', ready: true },
      { label: 'Assignments', route: '/admin/assignments', icon: '◌', ready: false },
      { label: 'Study Materials', route: '/admin/study-materials', icon: '◌', ready: false },
    ],
  },
  {
    title: 'Communication',
    items: [
      { label: 'Notices', route: '/admin/notices', icon: '◌', ready: false },
      { label: 'Documents', route: '/admin/documents', icon: '◌', ready: false },
    ],
  },
  {
    title: 'Intelligence',
    items: [
      { label: 'AI Assistant', route: '/admin/ai', icon: '◌', ready: false },
      { label: 'Performance Analytics', route: '/admin/performance', icon: '◌', ready: false },
      { label: 'Predictions', route: '/admin/predictions', icon: '◌', ready: false },
    ],
  },
  {
    title: 'System',
    items: [
      { label: 'Profile Settings', route: '/admin/profile', icon: '◌', ready: false },
      { label: 'System Settings', route: '/admin/settings', icon: '◌', ready: false },
    ],
  },
];

export const clearAuthState = () => {
  localStorage.removeItem('smart_college_token');
  localStorage.removeItem('smart_college_user');
};

/**
 * The sidebar, and on narrow screens the drawer that holds it.
 *
 * The open/closed state lives here rather than in a context or in each page,
 * because this component is rendered by every admin screen — putting it here
 * means the drawer works everywhere without a single page knowing about it.
 */
export default function AdminSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const toggleRef = useRef(null);
  const drawerRef = useRef(null);

  const go = (route) => {
    navigate(route);
    setOpen(false);
  };

  const handleLogout = () => {
    clearAuthState();
    navigate('/login');
    window.location.reload();
  };

  // Escape closes, and focus goes back to the control that opened it —
  // otherwise a keyboard user is left at the top of the document.
  useEffect(() => {
    if (!open) return undefined;

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);

    // The page behind a drawer must not scroll with it.
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    drawerRef.current?.focus();

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <>
      <button
        ref={toggleRef}
        type="button"
        className="sidebar-toggle"
        aria-expanded={open}
        aria-controls="admin-sidebar"
        aria-label={open ? 'Close navigation' : 'Open navigation'}
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">{open ? '✕' : '☰'}</span>
      </button>

      {open && (
        <div
          className="sidebar-overlay"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        id="admin-sidebar"
        ref={drawerRef}
        tabIndex={-1}
        className={`sidebar ${open ? 'is-open' : ''}`}
      >
        <div className="brand-box">
          <div className="brand-mark" aria-hidden="true">S</div>
          <div className="brand-text">
            <span className="brand-main">SMART COLLEGE</span>
            <span className="brand-sub">SYSTEM</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Admin sections">
          {navGroups.map((group) => (
            <div className="nav-group" key={group.title}>
              <span className="nav-group-title">{group.title}</span>
              {group.items.map((item) => {
                const isActive = location.pathname === item.route;
                return (
                  <button
                    key={item.label}
                    className={`nav-item ${isActive ? 'active' : ''} ${item.ready ? '' : 'upcoming'}`}
                    type="button"
                    onClick={() => item.ready && go(item.route)}
                    disabled={!item.ready}
                    aria-current={isActive ? 'page' : undefined}
                    title={item.ready ? item.label : `${item.label} — coming soon`}
                  >
                    {/* Decorative glyphs; a screen reader would otherwise
                        announce them by their symbol names. */}
                    <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                    <span className="nav-label">{item.label}</span>
                    {!item.ready && <span className="nav-soon">soon</span>}
                  </button>
                );
              })}
            </div>
          ))}

          <div className="nav-group">
            <button className="nav-item logout" type="button" onClick={handleLogout}>
              <span className="nav-icon" aria-hidden="true">⏻</span>
              <span className="nav-label">Logout</span>
            </button>
          </div>
        </nav>
      </aside>
    </>
  );
}
