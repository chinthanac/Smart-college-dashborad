import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminSidebar from '../components/AdminSidebar';

const SECTIONS_API_URL = 'http://localhost:8000/api/sections';
const COURSES_API_URL = 'http://localhost:8000/api/courses';
const ACADEMIC_YEARS_API_URL = 'http://localhost:8000/api/academic-years';
const SEMESTERS_API_URL = 'http://localhost:8000/api/semesters';

const emptyForm = {
  course_id: '',
  academic_year_id: '',
  semester_id: '',
  name: '',
  code: '',
  capacity: '60',
  room_number: '',
  is_active: true,
};

export default function SectionsPage() {
  const navigate = useNavigate();
  const [sections, setSections] = useState([]);
  const [courses, setCourses] = useState([]);
  const [academicYears, setAcademicYears] = useState([]);
  const [semesters, setSemesters] = useState([]);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ course_id: '', academic_year_id: '', semester_id: '' });
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

  const fetchSemesters = async (courseId = '', academicYearId = '') => {
    if (!token) {
      navigate('/login');
      return [];
    }
    try {
      const params = {};
      if (courseId) params.course_id = courseId;
      if (academicYearId) params.academic_year_id = academicYearId;
      const response = await axios.get(SEMESTERS_API_URL, {
        params,
        headers: { Authorization: `Bearer ${token}` },
      });
      setSemesters(response.data);
      return response.data;
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load semesters.');
      return [];
    }
  };

  const fetchSections = async (semesterFilter = '') => {
    if (!token) {
      navigate('/login');
      return;
    }
    try {
      const params = {};
      if (semesterFilter) params.semester_id = semesterFilter;
      if (filters.course_id) params.course_id = filters.course_id;
      if (filters.academic_year_id) params.academic_year_id = filters.academic_year_id;
      const response = await axios.get(SECTIONS_API_URL, {
        params,
        headers: { Authorization: `Bearer ${token}` },
      });
      setSections(response.data);
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load sections.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      await Promise.all([fetchCourses(), fetchAcademicYears()]);
      await fetchSemesters();
      await fetchSections();
    };
    loadData();
  }, []);

  useEffect(() => {
    const loadFilteredSemesters = async () => {
      const courseId = filters.course_id || '';
      const academicYearId = filters.academic_year_id || '';
      const list = await fetchSemesters(courseId, academicYearId);
      if (form.semester_id && !list.some((item) => String(item.id) === String(form.semester_id))) {
        setForm((current) => ({ ...current, semester_id: '' }));
      }
      if (!filters.semester_id && list.length) {
        setFilters((current) => ({ ...current, semester_id: '' }));
      }
    };
    loadFilteredSemesters();
  }, [filters.course_id, filters.academic_year_id]);

  useEffect(() => {
    fetchSections(filters.semester_id);
  }, [filters.course_id, filters.academic_year_id, filters.semester_id]);

  const filteredSections = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return sections;
    return sections.filter((item) => (
      (item.name || '').toLowerCase().includes(query) ||
      (item.code || '').toLowerCase().includes(query) ||
      (item.room_number || '').toLowerCase().includes(query) ||
      (item.course_name || '').toLowerCase().includes(query) ||
      (item.academic_year_name || '').toLowerCase().includes(query) ||
      (item.semester_name || '').toLowerCase().includes(query)
    ));
  }, [sections, search]);

  const openCreateModal = async () => {
    setEditingId(null);
    setError('');
    const courseList = await fetchCourses();
    const academicYearList = await fetchAcademicYears();
    const semesterList = await fetchSemesters(courseList[0]?.id || '', academicYearList[0]?.id || '');
    setForm({
      ...emptyForm,
      course_id: courseList[0]?.id ? String(courseList[0].id) : '',
      academic_year_id: academicYearList[0]?.id ? String(academicYearList[0].id) : '',
      semester_id: semesterList[0]?.id ? String(semesterList[0].id) : '',
    });
    setModalOpen(true);

    if (!courseList.length || !academicYearList.length || !semesterList.length) {
      setError('Please create a course, academic year, and semester before adding a section.');
    }
  };

  const openEditModal = (section) => {
    setEditingId(section.id);
    setForm({
      course_id: section.course_id || '',
      academic_year_id: section.academic_year_id || '',
      semester_id: String(section.semester_id),
      name: section.name,
      code: section.code,
      capacity: String(section.capacity),
      room_number: section.room_number,
      is_active: section.is_active,
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
    if (!form.semester_id || !form.name.trim() || !form.code.trim() || !form.room_number.trim()) {
      setError('Semester, section name, code, and room are required.');
      return;
    }
    if (Number(form.capacity) <= 0) {
      setError('Capacity must be positive.');
      return;
    }

    setSaving(true);
    setError('');

    const payload = {
      semester_id: Number(form.semester_id),
      name: form.name.trim(),
      code: form.code.trim(),
      capacity: Number(form.capacity),
      room_number: form.room_number.trim(),
      is_active: form.is_active,
    };

    try {
      if (editingId) {
        await axios.put(`${SECTIONS_API_URL}/${editingId}`, { ...payload, is_active: true }, {
          headers: { Authorization: `Bearer ${token}` },
        });
      } else {
        await axios.post(SECTIONS_API_URL, payload, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }
      closeModal();
      fetchSections(filters.semester_id);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Operation failed.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    const confirmed = window.confirm('Are you sure you want to delete this section?');
    if (!confirmed) return;

    try {
      await axios.delete(`${SECTIONS_API_URL}/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchSections(filters.semester_id);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not delete section.');
    }
  };

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar" style={{ paddingBottom: '12px' }}>
          <div className="welcome-text">
            <strong>Sections</strong>
          </div>

          <div className="topbar-right">
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Add Section
            </button>
          </div>
        </header>

        <div className="department-toolbar" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(160px, 1fr))', gap: '12px' }}>
          <select
            className="department-search"
            value={filters.course_id}
            onChange={(e) => setFilters((current) => ({ ...current, course_id: e.target.value, academic_year_id: '', semester_id: '' }))}
          >
            <option value="">All Courses</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>{course.name}</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.academic_year_id}
            onChange={(e) => setFilters((current) => ({ ...current, academic_year_id: e.target.value, semester_id: '' }))}
          >
            <option value="">All Academic Years</option>
            {academicYears.map((year) => (
              <option key={year.id} value={year.id}>{year.name}</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.semester_id}
            onChange={(e) => setFilters((current) => ({ ...current, semester_id: e.target.value }))}
          >
            <option value="">All Semesters</option>
            {semesters
              .filter((semester) => (
                (!filters.course_id || String(semester.course_id) === String(filters.course_id)) &&
                (!filters.academic_year_id || String(semester.academic_year_id) === String(filters.academic_year_id))
              ))
              .map((semester) => (
                <option key={semester.id} value={semester.id}>{semester.name}</option>
              ))}
          </select>

          <input
            className="department-search"
            type="text"
            placeholder="Search sections..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ gridColumn: '1 / -1' }}
          />
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="department-table-wrap">
          <table className="department-table">
            <thead>
              <tr>
                <th>Course</th>
                <th>Year</th>
                <th>Semester</th>
                <th>Section</th>
                <th>Room</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" className="table-loading">Loading sections...</td>
                </tr>
              ) : filteredSections.length === 0 ? (
                <tr>
                  <td colSpan="7" className="table-empty">No sections found.</td>
                </tr>
              ) : (
                filteredSections.map((item) => (
                  <tr key={item.id}>
                    <td>{item.course_name || '—'}</td>
                    <td>{item.academic_year_name || '—'}</td>
                    <td>{item.semester_name || '—'}</td>
                    <td>
                      <div className="dept-name">{item.name}</div>
                      <div className="dept-desc">Code: {item.code}</div>
                    </td>
                    <td>{item.room_number}</td>
                    <td>
                      <span className={`status-badge ${item.is_active ? 'active' : 'inactive'}`}>
                        {item.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
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
            <h3>{editingId ? 'Edit Section' : 'Add New Section'}</h3>
            <form onSubmit={handleSubmit} className="department-form">
              <label>
                Course
                <select value={form.course_id} onChange={(e) => {
                  const nextCourseId = e.target.value;
                  setForm({ ...form, course_id: nextCourseId, academic_year_id: '', semester_id: '' });
                  fetchSemesters(nextCourseId, '');
                }} disabled={!courses.length}>
                  <option value="">{courses.length ? 'Select course' : 'No courses available'}</option>
                  {courses.map((course) => (
                    <option key={course.id} value={course.id}>{course.name}</option>
                  ))}
                </select>
              </label>

              <label>
                Academic Year
                <select value={form.academic_year_id} onChange={(e) => {
                  const nextAcademicYearId = e.target.value;
                  setForm({ ...form, academic_year_id: nextAcademicYearId, semester_id: '' });
                  fetchSemesters(form.course_id, nextAcademicYearId);
                }} disabled={!academicYears.length}>
                  <option value="">{academicYears.length ? 'Select academic year' : 'No academic years available'}</option>
                  {academicYears.map((year) => (
                    <option key={year.id} value={year.id}>{year.name}</option>
                  ))}
                </select>
              </label>

              <label>
                Semester
                <select value={form.semester_id} onChange={(e) => setForm({ ...form, semester_id: e.target.value })} disabled={!semesters.length}>
                  <option value="">{semesters.length ? 'Select semester' : 'No semesters available'}</option>
                  {semesters
                    .filter((semester) => (
                      (!form.course_id || String(semester.course_id) === String(form.course_id)) &&
                      (!form.academic_year_id || String(semester.academic_year_id) === String(form.academic_year_id))
                    ))
                    .map((semester) => (
                      <option key={semester.id} value={semester.id}>{semester.name}</option>
                    ))}
                </select>
              </label>

              <label>
                Section Name
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Section A" />
              </label>

              <label>
                Section Code
                <input type="text" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="A" />
              </label>

              <label>
                Student Capacity
                <input type="number" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} placeholder="60" min="1" />
              </label>

              <label>
                Room Number
                <input type="text" value={form.room_number} onChange={(e) => setForm({ ...form, room_number: e.target.value })} placeholder="CSE-301" />
              </label>

              <label className="checkbox-row">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                <span>Active</span>
              </label>

              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={closeModal}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={saving}>{saving ? 'Saving...' : editingId ? 'Update Section' : 'Create Section'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
