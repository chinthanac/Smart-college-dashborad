import { Navigate, Route, Routes } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import AdminDashboard from './pages/AdminDashboard';
import DepartmentsPage from './pages/DepartmentsPage';
import CoursesPage from './pages/CoursesPage';
import AcademicYearsPage from './pages/AcademicYearsPage';
import SemestersPage from './pages/SemestersPage';
import SectionsPage from './pages/SectionsPage';
import FacultyPage from './pages/FacultyPage';
import FacultyDashboard from './pages/FacultyDashboard';
import StudentsPage from './pages/StudentsPage';
import StudentDashboard from './pages/StudentDashboard';
import Subjects from './pages/admin/subjects/Subjects';
import TeachingAssignments from './pages/admin/teaching-assignments/TeachingAssignments';
import Timetable from './pages/admin/timetable/Timetable';
import Attendance from './pages/admin/attendance/Attendance';
import MarkAttendance from './pages/faculty/attendance/MarkAttendance';
import Assessments from './pages/admin/assessments/Assessments';
import Results from './pages/admin/results/Results';
import EnterMarks from './pages/faculty/marks/EnterMarks';

const getToken = () => localStorage.getItem('smart_college_token');

const getRole = () => {
  try {
    return JSON.parse(localStorage.getItem('smart_college_user') || '{}').role || '';
  } catch {
    return '';
  }
};

const dashboardFor = (role) => {
  if (role === 'FACULTY') return '/faculty/dashboard';
  if (role === 'STUDENT') return '/student/dashboard';
  return '/admin/dashboard';
};

function ProtectedRoute({ children, role }) {
  const token = getToken();
  if (!token) return <Navigate to="/login" replace />;

  // a signed-in faculty member never lands on an Admin screen
  if (role && getRole() !== role) {
    return <Navigate to={dashboardFor(getRole())} replace />;
  }
  return children;
}

const adminRoutes = [
  { path: '/admin/dashboard', element: <AdminDashboard /> },
  { path: '/admin/departments', element: <DepartmentsPage /> },
  { path: '/admin/courses', element: <CoursesPage /> },
  { path: '/admin/academic-years', element: <AcademicYearsPage /> },
  { path: '/admin/semesters', element: <SemestersPage /> },
  { path: '/admin/sections', element: <SectionsPage /> },
  { path: '/admin/faculty', element: <FacultyPage /> },
  { path: '/admin/students', element: <StudentsPage /> },
  { path: '/admin/subjects', element: <Subjects /> },
  { path: '/admin/teaching-assignments', element: <TeachingAssignments /> },
  { path: '/admin/timetable', element: <Timetable /> },
  { path: '/admin/attendance', element: <Attendance /> },
  { path: '/admin/assessments', element: <Assessments /> },
  { path: '/admin/results', element: <Results /> },
];

/**
 * The admin routes that actually exist.
 *
 * Exported so a caller can check a link before rendering it: the dashboard
 * used to offer "Create Notice" and "Upload Material", neither of which was
 * a route, so both fell through the catch-all below and logged the admin out.
 */
export const adminRoutePaths = adminRoutes.map((route) => route.path);

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {adminRoutes.map((route) => (
        <Route
          key={route.path}
          path={route.path}
          element={<ProtectedRoute role="ADMIN">{route.element}</ProtectedRoute>}
        />
      ))}

      <Route
        path="/student/dashboard"
        element={
          <ProtectedRoute role="STUDENT">
            <StudentDashboard />
          </ProtectedRoute>
        }
      />

      <Route
        path="/faculty/dashboard"
        element={
          <ProtectedRoute role="FACULTY">
            <FacultyDashboard />
          </ProtectedRoute>
        }
      />

      <Route
        path="/faculty/attendance"
        element={
          <ProtectedRoute role="FACULTY">
            <MarkAttendance />
          </ProtectedRoute>
        }
      />

      <Route
        path="/faculty/marks"
        element={
          <ProtectedRoute role="FACULTY">
            <EnterMarks />
          </ProtectedRoute>
        }
      />

      {/* An unknown URL should not sign anybody out. */}
      <Route
        path="*"
        element={
          getToken()
            ? <Navigate to={dashboardFor(getRole())} replace />
            : <Navigate to="/login" replace />
        }
      />
    </Routes>
  );
}
