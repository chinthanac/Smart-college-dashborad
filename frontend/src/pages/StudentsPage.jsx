import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminSidebar from '../components/AdminSidebar';
import StudentAcademicPanel from '../components/students/StudentAcademicPanel';

const API = 'http://localhost:8000/api';
const STUDENTS_API_URL = `${API}/students`;

const PAGE_SIZES = [10, 25, 50, 100];

const STATUS_TONE = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  GRADUATED: 'graduated',
  SUSPENDED: 'suspended',
};

const emptyForm = {
  student_id: '',
  first_name: '',
  last_name: '',
  date_of_birth: '',
  gender: '',
  phone: '',
  address: '',
  email: '',
  password: '',
  department_id: '',
  course_id: '',
  academic_year_id: '',
  semester_id: '',
  section_id: '',
  admission_date: '',
  status: 'ACTIVE',
};

const emptyFilters = {
  department_id: '',
  course_id: '',
  academic_year_id: '',
  semester_id: '',
  section_id: '',
  status: '',
};

const formatDate = (value) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
};

export default function StudentsPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');
  const authHeaders = useMemo(() => ({ headers: { Authorization: `Bearer ${token}` } }), [token]);

  const [students, setStudents] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [genders, setGenders] = useState([]);
  const [statuses, setStatuses] = useState([]);

  // dependent dropdown data, kept separately for the filter bar and the form
  // so that changing a filter never disturbs a half-filled form
  const [filterOptions, setFilterOptions] = useState({ courses: [], years: [], semesters: [], sections: [] });
  const [formOptions, setFormOptions] = useState({ courses: [], years: [], semesters: [], sections: [] });

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filters, setFilters] = useState(emptyFilters);
  const [sort, setSort] = useState({ key: 'student_id', direction: 'asc' });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const [detailsFor, setDetailsFor] = useState(null);
  const [credentials, setCredentials] = useState(null);
  const [busyRowId, setBusyRowId] = useState(null);

  // ---------------------------------------------------------------- data

  const get = useCallback(
    async (url, params) => {
      const response = await axios.get(url, { ...authHeaders, params });
      return response.data;
    },
    [authHeaders],
  );

  const fetchStudents = useCallback(async () => {
    try {
      const params = {};
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params[key] = value;
      });
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();

      setStudents(await get(STUDENTS_API_URL, params));
      setError('');
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/login');
        return;
      }
      setError(err?.response?.data?.detail || 'Unable to load students.');
    } finally {
      setLoading(false);
    }
  }, [get, filters, debouncedSearch, navigate]);

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }
    const loadReferenceData = async () => {
      try {
        const [departmentList, options] = await Promise.all([
          get(`${API}/departments`),
          get(`${STUDENTS_API_URL}/options`),
        ]);
        setDepartments(departmentList);
        setGenders(options.genders);
        setStatuses(options.statuses);
      } catch (err) {
        setError(err?.response?.data?.detail || 'Unable to load reference data.');
      }
    };
    loadReferenceData();
  }, [token, navigate, get]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!token) return;
    fetchStudents();
  }, [token, fetchStudents]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, filters, pageSize]);

  /**
   * Walks the chain from whichever level changed and reloads only the
   * levels below it: Department → Course → Year → Semester → Section.
   * Each level is fetched from its own filtered endpoint rather than
   * pulling everything down and filtering in the browser.
   */
  const loadChain = useCallback(
    async (selection, setOptions) => {
      const next = { courses: [], years: [], semesters: [], sections: [] };
      try {
        if (selection.department_id) {
          next.courses = await get(`${API}/courses`, { department_id: selection.department_id });
        }
        if (selection.course_id) {
          next.years = await get(`${API}/academic-years`, { course_id: selection.course_id });
        }
        if (selection.course_id && selection.academic_year_id) {
          next.semesters = await get(`${API}/semesters`, {
            course_id: selection.course_id,
            academic_year_id: selection.academic_year_id,
          });
        }
        if (selection.semester_id) {
          next.sections = await get(`${API}/sections`, { semester_id: selection.semester_id });
        }
        setOptions(next);
        return next;
      } catch (err) {
        setError(err?.response?.data?.detail || 'Unable to load academic options.');
        setOptions(next);
        return next;
      }
    },
    [get],
  );

  useEffect(() => {
    if (!token) return;
    loadChain(filters, setFilterOptions);
  }, [token, loadChain, filters.department_id, filters.course_id, filters.academic_year_id, filters.semester_id]);

  // --------------------------------------------------- derived state

  const stats = useMemo(() => {
    const counts = { ACTIVE: 0, INACTIVE: 0, GRADUATED: 0, SUSPENDED: 0 };
    students.forEach((item) => {
      counts[item.status] = (counts[item.status] || 0) + 1;
    });
    return { total: students.length, ...counts };
  }, [students]);

  const sortedStudents = useMemo(() => {
    const rows = [...students];
    const { key, direction } = sort;
    const factor = direction === 'asc' ? 1 : -1;

    rows.sort((a, b) => {
      let left = a[key];
      let right = b[key];
      if (key === 'name') {
        left = a.full_name;
        right = b.full_name;
      }
      if (key === 'semester_number') {
        return ((left ?? 0) - (right ?? 0)) * factor;
      }
      return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true }) * factor;
    });
    return rows;
  }, [students, sort]);

  const totalPages = Math.max(1, Math.ceil(sortedStudents.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleStudents = useMemo(
    () => sortedStudents.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [sortedStudents, currentPage, pageSize],
  );

  const activeFilterCount = Object.values(filters).filter(Boolean).length + (search.trim() ? 1 : 0);

  const toggleSort = (key) => {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const sortIndicator = (key) => (sort.key !== key ? '' : sort.direction === 'asc' ? ' ▲' : ' ▼');

  // --------------------------------------------------------- filters

  /** Clearing a level clears every level beneath it. */
  const setFilterLevel = (level) => (event) => {
    const value = event.target.value;
    setFilters((current) => {
      const next = { ...current, [level]: value };
      const chain = ['department_id', 'course_id', 'academic_year_id', 'semester_id', 'section_id'];
      chain.slice(chain.indexOf(level) + 1).forEach((key) => {
        next[key] = '';
      });
      return next;
    });
  };

  const resetFilters = () => {
    setFilters(emptyFilters);
    setSearch('');
  };

  // ----------------------------------------------------------- modal

  const openCreateModal = () => {
    setEditingId(null);
    setForm({ ...emptyForm, admission_date: new Date().toISOString().slice(0, 10) });
    setFormOptions({ courses: [], years: [], semesters: [], sections: [] });
    setFormErrors({});
    setError('');
    setModalOpen(true);

    if (!departments.length) {
      setError('Create a department, course, academic year, semester, and section before adding students.');
    }
  };

  const openEditModal = async (student) => {
    setEditingId(student.id);
    const next = {
      student_id: student.student_id,
      first_name: student.first_name,
      last_name: student.last_name,
      date_of_birth: student.date_of_birth || '',
      gender: student.gender || '',
      phone: student.phone,
      address: student.address || '',
      email: student.email,
      password: '',
      department_id: String(student.department_id),
      course_id: String(student.course_id),
      academic_year_id: String(student.academic_year_id),
      semester_id: String(student.semester_id),
      section_id: String(student.section_id),
      admission_date: student.admission_date || '',
      status: student.status,
    };
    setForm(next);
    setFormErrors({});
    setError('');
    setModalOpen(true);
    await loadChain(next, setFormOptions);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setForm(emptyForm);
    setFormErrors({});
  };

  const setField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
    setFormErrors((current) => ({ ...current, [field]: '' }));
  };

  /** Selecting an academic level resets and reloads everything below it. */
  const setFormLevel = (level) => async (event) => {
    const value = event.target.value;
    const chain = ['department_id', 'course_id', 'academic_year_id', 'semester_id', 'section_id'];
    const next = { ...form, [level]: value };
    chain.slice(chain.indexOf(level) + 1).forEach((key) => {
      next[key] = '';
    });

    setForm(next);
    setFormErrors((current) => ({ ...current, [level]: '' }));
    await loadChain(next, setFormOptions);
  };

  const suggestStudentId = async () => {
    if (!form.department_id || !form.academic_year_id) {
      setError('Choose a department and academic year first, then the ID can be suggested.');
      return;
    }
    try {
      const data = await get(`${STUDENTS_API_URL}/suggest-id`, {
        department_id: form.department_id,
        academic_year_id: form.academic_year_id,
      });
      setForm((current) => ({ ...current, student_id: data.suggested_student_id }));
      setFormErrors((current) => ({ ...current, student_id: '' }));
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not suggest a student ID.');
    }
  };

  const generatePassword = () => {
    const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
    const lower = 'abcdefghijkmnpqrstuvwxyz';
    const digits = '23456789';
    const symbols = '!@#$%';
    const all = upper + lower + digits + symbols;
    const pick = (set) => set[Math.floor(Math.random() * set.length)];
    const chars = [pick(upper), pick(lower), pick(digits), pick(symbols)];
    while (chars.length < 12) chars.push(pick(all));
    setForm((current) => ({
      ...current,
      password: chars.sort(() => Math.random() - 0.5).join(''),
    }));
    setFormErrors((current) => ({ ...current, password: '' }));
  };

  const validateForm = () => {
    const errors = {};
    if (!form.student_id.trim()) errors.student_id = 'Student ID is required.';
    if (!form.first_name.trim()) errors.first_name = 'First name is required.';
    if (!form.last_name.trim()) errors.last_name = 'Last name is required.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(form.email.trim())) errors.email = 'Enter a valid email address.';
    if (!/^\+?[0-9]{10,15}$/.test(form.phone.replace(/[\s()-]/g, ''))) {
      errors.phone = 'Phone must be 10 to 15 digits.';
    }
    if (!form.department_id) errors.department_id = 'Select a department.';
    if (!form.course_id) errors.course_id = 'Select a course.';
    if (!form.academic_year_id) errors.academic_year_id = 'Select an academic year.';
    if (!form.semester_id) errors.semester_id = 'Select a semester.';
    if (!form.section_id) errors.section_id = 'Select a section.';
    if (form.password && form.password.length < 8) {
      errors.password = 'Temporary password must be at least 8 characters.';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!validateForm()) return;

    setSaving(true);
    setError('');

    const payload = {
      student_id: form.student_id.trim().toUpperCase(),
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      date_of_birth: form.date_of_birth || null,
      gender: form.gender || null,
      phone: form.phone.replace(/[\s()-]/g, ''),
      address: form.address.trim() || null,
      email: form.email.trim().toLowerCase(),
      department_id: Number(form.department_id),
      course_id: Number(form.course_id),
      academic_year_id: Number(form.academic_year_id),
      semester_id: Number(form.semester_id),
      section_id: Number(form.section_id),
      admission_date: form.admission_date || null,
      status: form.status,
    };

    try {
      if (editingId) {
        await axios.put(`${STUDENTS_API_URL}/${editingId}`, payload, authHeaders);
        setNotice(`${payload.first_name} ${payload.last_name} was updated.`);
      } else {
        const response = await axios.post(
          STUDENTS_API_URL,
          { ...payload, password: form.password || null },
          authHeaders,
        );
        setCredentials({
          name: response.data.full_name,
          email: response.data.email,
          password: response.data.generated_password || form.password,
          generated: Boolean(response.data.generated_password),
        });
        setNotice(`${response.data.full_name} was enrolled.`);
      }
      closeModal();
      fetchStudents();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Operation failed.');
    } finally {
      setSaving(false);
    }
  };

  // ---------------------------------------------------- row actions

  const changeStatus = async (student, nextStatus) => {
    if (student.status === nextStatus) return;
    if (!window.confirm(`Set ${student.full_name} to ${nextStatus}?`)) return;

    setBusyRowId(student.id);
    try {
      if (nextStatus === 'ACTIVE') {
        await axios.patch(`${STUDENTS_API_URL}/${student.id}/activate`, {}, authHeaders);
      } else if (nextStatus === 'INACTIVE') {
        await axios.patch(`${STUDENTS_API_URL}/${student.id}/deactivate`, {}, authHeaders);
      } else {
        await axios.patch(`${STUDENTS_API_URL}/${student.id}/status`, { status: nextStatus }, authHeaders);
      }
      setNotice(`${student.full_name} is now ${nextStatus}.`);
      fetchStudents();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not change the status.');
    } finally {
      setBusyRowId(null);
    }
  };

  const handleResetPassword = async (student) => {
    if (!window.confirm(`Generate a new password for ${student.full_name}?`)) return;

    setBusyRowId(student.id);
    try {
      const response = await axios.post(`${STUDENTS_API_URL}/${student.id}/reset-password`, {}, authHeaders);
      setCredentials({
        name: response.data.full_name,
        email: response.data.email,
        password: response.data.generated_password,
        generated: true,
      });
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not reset the password.');
    } finally {
      setBusyRowId(null);
    }
  };

  const handleDelete = async (student) => {
    const confirmed = window.confirm(
      `Delete ${student.full_name} permanently?\n\nThis also removes their login account and will break any attendance, marks, or assignment history that references them.\n\nTo keep the record, set the status to INACTIVE or GRADUATED instead.`,
    );
    if (!confirmed) return;

    setBusyRowId(student.id);
    try {
      await axios.delete(`${STUDENTS_API_URL}/${student.id}`, authHeaders);
      setNotice(`${student.full_name} was deleted.`);
      fetchStudents();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not delete this student.');
    } finally {
      setBusyRowId(null);
    }
  };

  const copyCredentials = async () => {
    if (!credentials) return;
    try {
      await navigator.clipboard.writeText(`Email: ${credentials.email}\nPassword: ${credentials.password}`);
      setNotice('Credentials copied to the clipboard.');
    } catch {
      setError('Could not copy automatically — please copy the credentials manually.');
    }
  };

  // ---------------------------------------------------------- render

  const chainSelect = (level, label, items, options, getLabel) => (
    <label>
      {label}
      <select value={form[level]} onChange={setFormLevel(level)} disabled={options.disabled}>
        <option value="">{options.placeholder}</option>
        {items.map((item) => (
          <option key={item.id} value={item.id}>{getLabel(item)}</option>
        ))}
      </select>
      {formErrors[level] && <span className="field-error">{formErrors[level]}</span>}
    </label>
  );

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Student Management</strong>
            <span className="page-subtitle">
              Enrol students into the Department → Course → Year → Semester → Section structure.
            </span>
          </div>

          <div className="topbar-right">
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Add Student
            </button>
          </div>
        </header>

        <section className="mini-stats">
          <div className="mini-stat">
            <span className="mini-stat-label">Total Students</span>
            <strong className="mini-stat-value">{stats.total}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Active</span>
            <strong className="mini-stat-value tone-green">{stats.ACTIVE}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Inactive</span>
            <strong className="mini-stat-value tone-gray">{stats.INACTIVE}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Graduated</span>
            <strong className="mini-stat-value tone-blue">{stats.GRADUATED}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Suspended</span>
            <strong className="mini-stat-value tone-red">{stats.SUSPENDED}</strong>
          </div>
        </section>

        <div className="filter-bar student-filter-bar">
          <input
            className="department-search filter-search"
            type="search"
            placeholder="Search by name, student ID, email, or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <select className="department-search" value={filters.department_id} onChange={setFilterLevel('department_id')}>
            <option value="">All Departments</option>
            {departments.map((item) => (
              <option key={item.id} value={item.id}>{item.name} ({item.code})</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.course_id}
            onChange={setFilterLevel('course_id')}
            disabled={!filters.department_id}
          >
            <option value="">{filters.department_id ? 'All Courses' : 'All Courses (pick a department)'}</option>
            {filterOptions.courses.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.academic_year_id}
            onChange={setFilterLevel('academic_year_id')}
            disabled={!filters.course_id}
          >
            <option value="">{filters.course_id ? 'All Academic Years' : 'All Years (pick a course)'}</option>
            {filterOptions.years.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.semester_id}
            onChange={setFilterLevel('semester_id')}
            disabled={!filters.academic_year_id}
          >
            <option value="">{filters.academic_year_id ? 'All Semesters' : 'All Semesters (pick a year)'}</option>
            {filterOptions.semesters.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.section_id}
            onChange={setFilterLevel('section_id')}
            disabled={!filters.semester_id}
          >
            <option value="">{filters.semester_id ? 'All Sections' : 'All Sections (pick a semester)'}</option>
            {filterOptions.sections.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.status}
            onChange={(e) => setFilters((current) => ({ ...current, status: e.target.value }))}
          >
            <option value="">All Statuses</option>
            {statuses.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>

          <button
            type="button"
            className="secondary-btn filter-reset"
            onClick={resetFilters}
            disabled={!activeFilterCount}
          >
            Clear{activeFilterCount ? ` (${activeFilterCount})` : ''}
          </button>
        </div>

        {error && (
          <div className="error-box dismissable" onClick={() => setError('')} role="alert">{error}</div>
        )}
        {notice && (
          <div className="success-box dismissable" onClick={() => setNotice('')} role="status">{notice}</div>
        )}

        <div className="department-table-wrap scroll-table">
          <table className="department-table faculty-table">
            <thead>
              <tr>
                <th className="sortable" onClick={() => toggleSort('student_id')}>ID{sortIndicator('student_id')}</th>
                <th className="sortable" onClick={() => toggleSort('name')}>Name{sortIndicator('name')}</th>
                <th className="sortable" onClick={() => toggleSort('department_code')}>Dept{sortIndicator('department_code')}</th>
                <th className="sortable" onClick={() => toggleSort('course_code')}>Course{sortIndicator('course_code')}</th>
                <th className="sortable" onClick={() => toggleSort('semester_number')}>Semester{sortIndicator('semester_number')}</th>
                <th className="sortable" onClick={() => toggleSort('section_name')}>Section{sortIndicator('section_name')}</th>
                <th className="sortable" onClick={() => toggleSort('status')}>Status{sortIndicator('status')}</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="8" className="table-loading">Loading students...</td></tr>
              ) : visibleStudents.length === 0 ? (
                <tr>
                  <td colSpan="8" className="table-empty">
                    {activeFilterCount
                      ? 'No students match the current filters.'
                      : 'No students yet. Use “+ Add Student” to enrol the first one.'}
                  </td>
                </tr>
              ) : (
                visibleStudents.map((item) => (
                  <tr key={item.id} className={item.status === 'ACTIVE' ? '' : 'row-inactive'}>
                    <td className="mono">{item.student_id}</td>
                    <td>
                      <button type="button" className="link-btn dept-name" onClick={() => setDetailsFor(item)}>
                        {item.full_name}
                      </button>
                      <div className="dept-desc">{item.email}</div>
                    </td>
                    <td>{item.department_code || '—'}</td>
                    <td>
                      <div>{item.course_code || '—'}</div>
                      <div className="dept-desc">{item.academic_year_name || ''}</div>
                    </td>
                    <td>{item.semester_number ?? '—'}</td>
                    <td>{item.section_name || '—'}</td>
                    <td>
                      <span className={`status-badge ${STATUS_TONE[item.status] || 'inactive'}`}>{item.status}</span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button type="button" className="table-btn view-btn" onClick={() => setDetailsFor(item)}>View</button>
                        <button type="button" className="table-btn edit-btn" onClick={() => openEditModal(item)}>Edit</button>
                        {item.status === 'ACTIVE' ? (
                          <button
                            type="button"
                            className="table-btn warn-btn"
                            onClick={() => changeStatus(item, 'INACTIVE')}
                            disabled={busyRowId === item.id}
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="table-btn success-btn"
                            onClick={() => changeStatus(item, 'ACTIVE')}
                            disabled={busyRowId === item.id}
                          >
                            Activate
                          </button>
                        )}
                        <select
                          className="row-status-select"
                          value={item.status}
                          onChange={(e) => changeStatus(item, e.target.value)}
                          disabled={busyRowId === item.id}
                          title="Change status"
                        >
                          {statuses.map((value) => (
                            <option key={value} value={value}>{value}</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="table-btn neutral-btn"
                          onClick={() => handleResetPassword(item)}
                          disabled={busyRowId === item.id}
                        >
                          Reset Password
                        </button>
                        <button
                          type="button"
                          className="table-btn delete-btn"
                          onClick={() => handleDelete(item)}
                          disabled={busyRowId === item.id}
                        >
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

        {!loading && sortedStudents.length > 0 && (
          <div className="table-footer">
            <span>
              Showing {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, sortedStudents.length)} of{' '}
              {sortedStudents.length}
            </span>
            <div className="pager">
              <label className="page-size">
                Rows
                <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
                  {PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>{size}</option>
                  ))}
                </select>
              </label>
              <button type="button" className="table-btn neutral-btn" onClick={() => setPage(currentPage - 1)} disabled={currentPage <= 1}>
                Previous
              </button>
              <span className="page-indicator">Page {currentPage} of {totalPages}</span>
              <button type="button" className="table-btn neutral-btn" onClick={() => setPage(currentPage + 1)} disabled={currentPage >= totalPages}>
                Next
              </button>
            </div>
          </div>
        )}
      </main>

      {/* -------------------------------------------------- add / edit */}
      {modalOpen && (
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal-card wide" onClick={(e) => e.stopPropagation()}>
            <h3>{editingId ? 'Edit Student' : 'Add Student'}</h3>
            <p className="modal-hint">
              {editingId
                ? 'Changing the email updates the linked login account. The academic chain is re-validated on save.'
                : 'A login account is created in the same transaction — if either record fails, neither is written.'}
            </p>

            <form onSubmit={handleSubmit} className="department-form form-grid">
              <div className="form-section span-2">Personal Information</div>

              <label>
                First Name
                <input type="text" value={form.first_name} onChange={setField('first_name')} placeholder="Rahul" />
                {formErrors.first_name && <span className="field-error">{formErrors.first_name}</span>}
              </label>

              <label>
                Last Name
                <input type="text" value={form.last_name} onChange={setField('last_name')} placeholder="Kumar" />
                {formErrors.last_name && <span className="field-error">{formErrors.last_name}</span>}
              </label>

              <label>
                Date of Birth
                <input type="date" value={form.date_of_birth} onChange={setField('date_of_birth')} />
              </label>

              <label>
                Gender
                <select value={form.gender} onChange={setField('gender')}>
                  <option value="">Not specified</option>
                  {genders.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>

              <label>
                Phone
                <input type="tel" value={form.phone} onChange={setField('phone')} placeholder="9876543210" />
                {formErrors.phone && <span className="field-error">{formErrors.phone}</span>}
              </label>

              <label>
                Admission Date
                <input type="date" value={form.admission_date} onChange={setField('admission_date')} />
              </label>

              <label className="span-2">
                Address
                <textarea rows="2" value={form.address} onChange={setField('address')} placeholder="12 College Road, Chennai" />
              </label>

              <div className="form-section span-2">Academic Information</div>

              <label>
                Department
                <select value={form.department_id} onChange={setFormLevel('department_id')} disabled={!departments.length}>
                  <option value="">{departments.length ? 'Select department' : 'No departments available'}</option>
                  {departments.map((item) => (
                    <option key={item.id} value={item.id}>{item.name} ({item.code})</option>
                  ))}
                </select>
                {formErrors.department_id && <span className="field-error">{formErrors.department_id}</span>}
              </label>

              {chainSelect('course_id', 'Course', formOptions.courses, {
                disabled: !form.department_id,
                placeholder: !form.department_id
                  ? 'Select a department first'
                  : formOptions.courses.length ? 'Select course' : 'No courses in this department',
              }, (item) => item.name)}

              {chainSelect('academic_year_id', 'Academic Year', formOptions.years, {
                disabled: !form.course_id,
                placeholder: !form.course_id
                  ? 'Select a course first'
                  : formOptions.years.length ? 'Select academic year' : 'No years with semesters for this course',
              }, (item) => item.name)}

              {chainSelect('semester_id', 'Semester', formOptions.semesters, {
                disabled: !form.academic_year_id,
                placeholder: !form.academic_year_id
                  ? 'Select an academic year first'
                  : formOptions.semesters.length ? 'Select semester' : 'No semesters for this course and year',
              }, (item) => item.name)}

              {chainSelect('section_id', 'Section', formOptions.sections, {
                disabled: !form.semester_id,
                placeholder: !form.semester_id
                  ? 'Select a semester first'
                  : formOptions.sections.length ? 'Select section' : 'No sections in this semester',
              }, (item) => `${item.name} (${item.room_number})`)}

              <label>
                Status
                <select value={form.status} onChange={setField('status')}>
                  {statuses.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>

              <div className="form-section span-2">Account Information</div>

              <label>
                Student ID
                <div className="input-with-action">
                  <input type="text" value={form.student_id} onChange={setField('student_id')} placeholder="CSE26001" />
                  <button type="button" className="table-btn neutral-btn" onClick={suggestStudentId}>Suggest</button>
                </div>
                {formErrors.student_id && <span className="field-error">{formErrors.student_id}</span>}
              </label>

              <label>
                Email
                <input type="email" value={form.email} onChange={setField('email')} placeholder="rahul@college.edu" />
                {formErrors.email && <span className="field-error">{formErrors.email}</span>}
              </label>

              {!editingId && (
                <label className="span-2">
                  Temporary Password
                  <div className="input-with-action">
                    <input
                      type="text"
                      value={form.password}
                      onChange={setField('password')}
                      placeholder="Leave empty and one will be generated"
                    />
                    <button type="button" className="table-btn neutral-btn" onClick={generatePassword}>Generate</button>
                  </div>
                  {formErrors.password && <span className="field-error">{formErrors.password}</span>}
                </label>
              )}

              <div className="modal-actions span-2">
                <button type="button" className="secondary-btn" onClick={closeModal}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={saving}>
                  {saving ? 'Saving...' : editingId ? 'Update Student' : 'Create Student'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------- profile */}
      {detailsFor && (
        <div className="modal-backdrop" onClick={() => setDetailsFor(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Student Profile</h3>

            <div className="profile-hero">
              <strong>{detailsFor.full_name}</strong>
              <span className="mono">{detailsFor.student_id}</span>
              <span className={`status-badge ${STATUS_TONE[detailsFor.status] || 'inactive'}`}>{detailsFor.status}</span>
            </div>

            <div className="profile-section-title">Personal</div>
            <div className="profile-grid">
              <div><span>Date of Birth</span><strong>{formatDate(detailsFor.date_of_birth)}</strong></div>
              <div><span>Gender</span><strong>{detailsFor.gender || '—'}</strong></div>
              <div><span>Phone</span><strong>{detailsFor.phone}</strong></div>
              <div><span>Admission Date</span><strong>{formatDate(detailsFor.admission_date)}</strong></div>
              <div className="span-2"><span>Address</span><strong>{detailsFor.address || '—'}</strong></div>
            </div>

            <div className="profile-section-title">Academic</div>
            <div className="profile-grid">
              <div><span>Department</span><strong>{detailsFor.department_name} ({detailsFor.department_code})</strong></div>
              <div><span>Course</span><strong>{detailsFor.course_name}</strong></div>
              <div><span>Academic Year</span><strong>{detailsFor.academic_year_name}</strong></div>
              <div><span>Semester</span><strong>{detailsFor.semester_name}</strong></div>
              <div><span>Section</span><strong>{detailsFor.section_name}</strong></div>
            </div>

            <div className="profile-section-title">Account</div>
            <div className="profile-grid">
              <div><span>Email</span><strong>{detailsFor.email}</strong></div>
              <div><span>Status</span><strong>{detailsFor.status}</strong></div>
            </div>

            <StudentAcademicPanel studentId={detailsFor.id} />

            <div className="modal-actions">
              <button type="button" className="secondary-btn" onClick={() => setDetailsFor(null)}>Close</button>
              <button
                type="button"
                className="primary-btn"
                onClick={() => {
                  const target = detailsFor;
                  setDetailsFor(null);
                  openEditModal(target);
                }}
              >
                Edit Student
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------- credentials */}
      {credentials && (
        <div className="modal-backdrop" onClick={() => setCredentials(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Login Credentials</h3>
            <p className="modal-hint">
              {credentials.generated
                ? `This password was generated and is shown once. Copy it now and give it to ${credentials.name}.`
                : `Give these credentials to ${credentials.name}. They should change the password after first login.`}
            </p>

            <div className="credentials-box">
              <div><span>Email</span><strong className="mono">{credentials.email}</strong></div>
              <div><span>Temporary Password</span><strong className="mono">{credentials.password}</strong></div>
            </div>

            <div className="modal-actions">
              <button type="button" className="secondary-btn" onClick={copyCredentials}>Copy</button>
              <button type="button" className="primary-btn" onClick={() => setCredentials(null)}>Done</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
