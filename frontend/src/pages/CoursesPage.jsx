import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminSidebar from '../components/AdminSidebar';

const API_URL = 'http://localhost:8000/api/courses';
const DEPARTMENTS_API_URL = 'http://localhost:8000/api/departments';

const emptyForm = {
  department_id: '',
  name: '',
  code: '',
  degree: '',
  duration_years: '4',
  description: '',
};

export default function CoursesPage() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const token = localStorage.getItem('smart_college_token');

  const handleLogout = () => {
    localStorage.removeItem('smart_college_token');
    localStorage.removeItem('smart_college_user');
    navigate('/login');
    window.location.reload();
  };

  const fetchDepartments = async () => {
    if (!token) {
      navigate('/login');
      return [];
    }

    try {
      const response = await axios.get(DEPARTMENTS_API_URL, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDepartments(response.data);
      return response.data;
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Unable to load departments.';
      setError(detail);
      return [];
    }
  };

  const fetchCourses = async () => {
    if (!token) {
      navigate('/login');
      return;
    }

    try {
      const response = await axios.get(API_URL, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCourses(response.data);
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load courses.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDepartments();
    fetchCourses();
  }, []);

  const filteredCourses = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return courses;

    return courses.filter((course) => {
      const departmentName = course.department_name || '';
      const departmentCode = course.department_code || '';
      return (
        course.name.toLowerCase().includes(query) ||
        course.code.toLowerCase().includes(query) ||
        departmentName.toLowerCase().includes(query) ||
        departmentCode.toLowerCase().includes(query)
      );
    });
  }, [courses, search]);

  const openCreateModal = async () => {
    setEditingId(null);
    setError('');

    const departmentList = await fetchDepartments();
    setForm({
      ...emptyForm,
      department_id: departmentList[0]?.id ? String(departmentList[0].id) : '',
    });
    setModalOpen(true);

    if (!departmentList.length) {
      setError('No departments found. Please create a department before adding a course.');
    }
  };

  const openEditModal = (course) => {
    setEditingId(course.id);
    setForm({
      department_id: String(course.department_id),
      name: course.name,
      code: course.code,
      degree: course.degree,
      duration_years: String(course.duration_years),
      description: course.description || '',
    });
    setModalOpen(true);
    setError('');
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setForm(emptyForm);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.department_id || !form.name || !form.code || !form.degree) {
      setError('Department, course name, code, and degree are required.');
      return;
    }

    setSaving(true);
    setError('');

    const payload = {
      department_id: Number(form.department_id),
      name: form.name,
      code: form.code,
      degree: form.degree,
      duration_years: Number(form.duration_years),
      description: form.description,
    };

    try {
      if (editingId) {
        await axios.put(`${API_URL}/${editingId}`, { ...payload, is_active: true }, {
          headers: { Authorization: `Bearer ${token}` },
        });
      } else {
        await axios.post(API_URL, payload, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }

      closeModal();
      fetchCourses();
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Operation failed.';
      setError(detail);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (courseId) => {
    const confirmed = window.confirm('Are you sure you want to delete this course?');
    if (!confirmed) return;

    try {
      await axios.delete(`${API_URL}/${courseId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchCourses();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not delete course.');
    }
  };

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar" style={{ paddingBottom: '12px' }}>
          <div className="welcome-text">
            <strong>Courses</strong>
          </div>

          <div className="topbar-right">
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Add Course
            </button>
          </div>
        </header>

        <div className="department-toolbar">
          <input
            className="department-search"
            type="text"
            placeholder="Search courses..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="department-table-wrap">
          <table className="department-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Course</th>
                <th>Department</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="4" className="table-loading">Loading courses...</td>
                </tr>
              ) : filteredCourses.length === 0 ? (
                <tr>
                  <td colSpan="4" className="table-empty">No courses found.</td>
                </tr>
              ) : (
                filteredCourses.map((course) => (
                  <tr key={course.id}>
                    <td>{course.code}</td>
                    <td>
                      <div className="dept-name">{course.name}</div>
                      <div className="dept-desc">{course.degree} • {course.duration_years} years</div>
                    </td>
                    <td>
                      <span className="status-badge active">
                        {course.department_code || course.department_name || 'Department'}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button type="button" className="table-btn edit-btn" onClick={() => openEditModal(course)}>
                          Edit
                        </button>
                        <button type="button" className="table-btn delete-btn" onClick={() => handleDelete(course.id)}>
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>

      {modalOpen && (
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>{editingId ? 'Edit Course' : 'Add New Course'}</h3>
            <form onSubmit={handleSubmit} className="department-form">
              <label>
                Department
                <select
                  value={form.department_id}
                  onChange={(e) => setForm({ ...form, department_id: e.target.value })}
                  disabled={!departments.length}
                >
                  <option value="">{departments.length ? 'Select department' : 'No departments available'}</option>
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Course Name
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="B.E. Computer Science & Engineering"
                />
              </label>

              <label>
                Course Code
                <input
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="BE-CSE"
                />
              </label>

              <label>
                Degree
                <input
                  type="text"
                  value={form.degree}
                  onChange={(e) => setForm({ ...form, degree: e.target.value })}
                  placeholder="Bachelor of Engineering"
                />
              </label>

              <label>
                Duration (Years)
                <input
                  type="number"
                  min="1"
                  max="6"
                  value={form.duration_years}
                  onChange={(e) => setForm({ ...form, duration_years: e.target.value })}
                />
              </label>

              <label>
                Description
                <textarea
                  rows="4"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Course description"
                />
              </label>

              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={closeModal}>
                  Cancel
                </button>
                <button type="submit" className="primary-btn" disabled={saving}>
                  {saving ? 'Saving...' : editingId ? 'Update Course' : 'Create Course'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
