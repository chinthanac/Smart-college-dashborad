import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminSidebar from '../components/AdminSidebar';

const SEMESTERS_API_URL = 'http://localhost:8000/api/semesters';
const COURSES_API_URL = 'http://localhost:8000/api/courses';
const ACADEMIC_YEARS_API_URL = 'http://localhost:8000/api/academic-years';

const emptyForm = {
  course_id: '',
  academic_year_id: '',
  semester_number: '1',
  name: '',
  start_date: '',
  end_date: '',
  is_active: true,
};

export default function SemestersPage() {
  const navigate = useNavigate();
  const [semesters, setSemesters] = useState([]);
  const [courses, setCourses] = useState([]);
  const [academicYears, setAcademicYears] = useState([]);
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

  const fetchCourses = async () => {
    if (!token) {
      navigate('/login');
      return [];
    }
    try {
      const response = await axios.get(COURSES_API_URL, { headers: { Authorization: `Bearer ${token}` } });
      setCourses(response.data);
      return response.data;
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load courses.');
      return [];
    }
  };

  const fetchAcademicYears = async () => {
    if (!token) {
      navigate('/login');
      return [];
    }
    try {
      const response = await axios.get(ACADEMIC_YEARS_API_URL, { headers: { Authorization: `Bearer ${token}` } });
      setAcademicYears(response.data);
      return response.data;
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load academic years.');
      return [];
    }
  };

  const fetchSemesters = async () => {
    if (!token) {
      navigate('/login');
      return;
    }
    try {
      const response = await axios.get(SEMESTERS_API_URL, { headers: { Authorization: `Bearer ${token}` } });
      setSemesters(response.data);
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load semesters.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      await Promise.all([fetchCourses(), fetchAcademicYears()]);
      await fetchSemesters();
    };
    loadData();
  }, []);

  const filteredSemesters = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return semesters;

    return semesters.filter((item) => {
      return (
        (item.name || '').toLowerCase().includes(query) ||
        (item.course_name || '').toLowerCase().includes(query) ||
        (item.academic_year_name || '').toLowerCase().includes(query)
      );
    });
  }, [semesters, search]);

  const openCreateModal = async () => {
    setEditingId(null);
    setError('');

    const [courseList, academicYearList] = await Promise.all([fetchCourses(), fetchAcademicYears()]);
    setForm({
      ...emptyForm,
      course_id: courseList[0]?.id ? String(courseList[0].id) : '',
      academic_year_id: academicYearList[0]?.id ? String(academicYearList[0].id) : '',
    });
    setModalOpen(true);

    if (!courseList.length || !academicYearList.length) {
      setError('Please create at least one course and one academic year before adding a semester.');
    }
  };

  const openEditModal = (item) => {
    setEditingId(item.id);
    setForm({
      course_id: String(item.course_id),
      academic_year_id: String(item.academic_year_id),
      semester_number: String(item.semester_number),
      name: item.name,
      start_date: item.start_date,
      end_date: item.end_date,
      is_active: item.is_active,
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
    if (!form.course_id || !form.academic_year_id || !form.start_date || !form.end_date) {
      setError('Course, academic year, and date range are required.');
      return;
    }

    const trimmedName = form.name.trim();
    if (!trimmedName) {
      setError('Semester name is required.');
      return;
    }

    if (new Date(form.end_date) <= new Date(form.start_date)) {
      setError('End date must be after the start date.');
      return;
    }

    setSaving(true);
    setError('');

    const payload = {
      course_id: Number(form.course_id),
      academic_year_id: Number(form.academic_year_id),
      semester_number: Number(form.semester_number),
      name: trimmedName,
      start_date: form.start_date,
      end_date: form.end_date,
      is_active: form.is_active,
    };

    try {
      if (editingId) {
        await axios.put(`${SEMESTERS_API_URL}/${editingId}`, { ...payload, is_active: true }, {
          headers: { Authorization: `Bearer ${token}` },
        });
      } else {
        await axios.post(SEMESTERS_API_URL, payload, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }

      closeModal();
      fetchSemesters();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Operation failed.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    const confirmed = window.confirm('Are you sure you want to delete this semester?');
    if (!confirmed) return;

    try {
      await axios.delete(`${SEMESTERS_API_URL}/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchSemesters();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not delete semester.');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: '2-digit' }).format(date);
  };

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar" style={{ paddingBottom: '12px' }}>
          <div className="welcome-text">
            <strong>Semesters</strong>
          </div>

          <div className="topbar-right">
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Add Semester
            </button>
          </div>
        </header>

        <div className="department-toolbar">
          <input
            className="department-search"
            type="text"
            placeholder="Search semesters..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="department-table-wrap">
          <table className="department-table">
            <thead>
              <tr>
                <th>Semester</th>
                <th>Course</th>
                <th>Academic Year</th>
                <th>Dates</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="5" className="table-loading">Loading semesters...</td>
                </tr>
              ) : filteredSemesters.length === 0 ? (
                <tr>
                  <td colSpan="5" className="table-empty">No semesters found.</td>
                </tr>
              ) : (
                filteredSemesters.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="dept-name">Semester {item.semester_number}</div>
                      <div className="dept-desc">{item.name}</div>
                    </td>
                    <td>{item.course_name || '—'}</td>
                    <td>{item.academic_year_name || '—'}</td>
                    <td>{formatDate(item.start_date)} - {formatDate(item.end_date)}</td>
                    <td>
                      <div className="action-buttons">
                        <button type="button" className="table-btn edit-btn" onClick={() => openEditModal(item)}>Edit</button>
                        <button type="button" className="table-btn delete-btn" onClick={() => handleDelete(item.id)}>Delete</button>
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
            <h3>{editingId ? 'Edit Semester' : 'Add Semester'}</h3>
            <form onSubmit={handleSubmit} className="department-form">
              <label>
                Course
                <select value={form.course_id} onChange={(e) => setForm({ ...form, course_id: e.target.value })} disabled={!courses.length}>
                  <option value="">{courses.length ? 'Select course' : 'No courses available'}</option>
                  {courses.map((course) => (
                    <option key={course.id} value={course.id}>{course.name}</option>
                  ))}
                </select>
              </label>

              <label>
                Academic Year
                <select value={form.academic_year_id} onChange={(e) => setForm({ ...form, academic_year_id: e.target.value })} disabled={!academicYears.length}>
                  <option value="">{academicYears.length ? 'Select academic year' : 'No academic years available'}</option>
                  {academicYears.map((year) => (
                    <option key={year.id} value={year.id}>{year.name}</option>
                  ))}
                </select>
              </label>

              <label>
                Semester Number
                <select value={form.semester_number} onChange={(e) => setForm({ ...form, semester_number: e.target.value })}>
                  {[1,2,3,4,5,6,7,8,9,10,11,12].map((num) => (
                    <option key={num} value={num}>{num}</option>
                  ))}
                </select>
              </label>

              <label>
                Semester Name
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Semester 5" />
              </label>

              <label>
                Start Date
                <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
              </label>

              <label>
                End Date
                <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
              </label>

              <label className="checkbox-row">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                <span>Active</span>
              </label>

              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={closeModal}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={saving}>{saving ? 'Saving...' : editingId ? 'Update Semester' : 'Create Semester'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
