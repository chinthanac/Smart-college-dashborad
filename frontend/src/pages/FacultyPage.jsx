import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminSidebar from '../components/AdminSidebar';
import FacultyTeachingPanel from '../components/faculty/FacultyTeachingPanel';

const FACULTY_API_URL = 'http://localhost:8000/api/faculty';
const DEPARTMENTS_API_URL = 'http://localhost:8000/api/departments';

const PAGE_SIZES = [10, 25, 50, 100];

const emptyForm = {
  faculty_id: '',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  department_id: '',
  designation: '',
  qualification: '',
  joining_date: '',
  employee_type: '',
  is_active: true,
};

const emptyFilters = {
  department_id: '',
  designation: '',
  employee_type: '',
  status: '',
};

const formatDate = (value) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
};

export default function FacultyPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem('smart_college_token');
  const authHeaders = useMemo(() => ({ headers: { Authorization: `Bearer ${token}` } }), [token]);

  const [faculty, setFaculty] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [designations, setDesignations] = useState([]);
  const [employeeTypes, setEmployeeTypes] = useState([]);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filters, setFilters] = useState(emptyFilters);
  const [sort, setSort] = useState({ key: 'faculty_id', direction: 'asc' });
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

  const fetchDepartments = useCallback(async () => {
    try {
      const response = await axios.get(DEPARTMENTS_API_URL, authHeaders);
      setDepartments(response.data);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load departments.');
    }
  }, [authHeaders]);

  const fetchOptions = useCallback(async () => {
    try {
      const response = await axios.get(`${FACULTY_API_URL}/options`, authHeaders);
      setDesignations(response.data.designations);
      setEmployeeTypes(response.data.employee_types);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load faculty options.');
    }
  }, [authHeaders]);

  const fetchFaculty = useCallback(async () => {
    try {
      const params = {};
      if (filters.department_id) params.department_id = filters.department_id;
      if (filters.designation) params.designation = filters.designation;
      if (filters.employee_type) params.employee_type = filters.employee_type;
      if (filters.status) params.is_active = filters.status === 'active';
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();

      const response = await axios.get(FACULTY_API_URL, { ...authHeaders, params });
      setFaculty(response.data);
      setError('');
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/login');
        return;
      }
      setError(err?.response?.data?.detail || 'Unable to load faculty.');
    } finally {
      setLoading(false);
    }
  }, [authHeaders, filters, debouncedSearch, navigate]);

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }
    fetchDepartments();
    fetchOptions();
  }, [token, navigate, fetchDepartments, fetchOptions]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!token) return;
    fetchFaculty();
  }, [token, fetchFaculty]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, filters, pageSize]);

  // ------------------------------------------------------- derived state

  const stats = useMemo(() => {
    const active = faculty.filter((item) => item.is_active).length;
    const departmentsCovered = new Set(faculty.map((item) => item.department_id)).size;
    return {
      total: faculty.length,
      active,
      inactive: faculty.length - active,
      departmentsCovered,
    };
  }, [faculty]);

  const sortedFaculty = useMemo(() => {
    const rows = [...faculty];
    const { key, direction } = sort;
    const factor = direction === 'asc' ? 1 : -1;

    rows.sort((a, b) => {
      let left = a[key];
      let right = b[key];

      if (key === 'name') {
        left = a.full_name;
        right = b.full_name;
      }
      if (key === 'joining_date') {
        return (new Date(left) - new Date(right)) * factor;
      }
      if (key === 'is_active') {
        return (Number(left) - Number(right)) * factor;
      }
      return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true }) * factor;
    });

    return rows;
  }, [faculty, sort]);

  const totalPages = Math.max(1, Math.ceil(sortedFaculty.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleFaculty = useMemo(
    () => sortedFaculty.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [sortedFaculty, currentPage, pageSize],
  );

  const activeFilterCount =
    Object.values(filters).filter(Boolean).length + (search.trim() ? 1 : 0);

  const toggleSort = (key) => {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const sortIndicator = (key) => {
    if (sort.key !== key) return '';
    return sort.direction === 'asc' ? ' ▲' : ' ▼';
  };

  // ------------------------------------------------------------- modals

  const openCreateModal = () => {
    setEditingId(null);
    setForm({
      ...emptyForm,
      department_id: departments[0]?.id ? String(departments[0].id) : '',
      designation: designations[0] || '',
      employee_type: employeeTypes[0] || '',
      joining_date: new Date().toISOString().slice(0, 10),
    });
    setFormErrors({});
    setError('');
    setModalOpen(true);

    if (!departments.length) {
      setError('Create a department before adding faculty.');
    }
  };

  const openEditModal = (item) => {
    setEditingId(item.id);
    setForm({
      faculty_id: item.faculty_id,
      first_name: item.first_name,
      last_name: item.last_name,
      email: item.email,
      phone: item.phone,
      department_id: String(item.department_id),
      designation: item.designation,
      qualification: item.qualification,
      joining_date: item.joining_date,
      employee_type: item.employee_type,
      is_active: item.is_active,
    });
    setFormErrors({});
    setError('');
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setForm(emptyForm);
    setFormErrors({});
  };

  const setField = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setForm((current) => ({ ...current, [field]: value }));
    setFormErrors((current) => ({ ...current, [field]: '' }));
  };

  const validateForm = () => {
    const errors = {};
    if (!form.faculty_id.trim()) errors.faculty_id = 'Faculty ID is required.';
    if (!form.first_name.trim()) errors.first_name = 'First name is required.';
    if (!form.last_name.trim()) errors.last_name = 'Last name is required.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(form.email.trim())) errors.email = 'Enter a valid email address.';
    if (!/^\+?[0-9]{10,15}$/.test(form.phone.replace(/[\s()-]/g, ''))) {
      errors.phone = 'Phone must be 10 to 15 digits.';
    }
    if (!form.department_id) errors.department_id = 'Select a department.';
    if (!form.designation) errors.designation = 'Select a designation.';
    if (!form.qualification.trim()) errors.qualification = 'Qualification is required.';
    if (!form.joining_date) errors.joining_date = 'Joining date is required.';
    if (!form.employee_type) errors.employee_type = 'Select an employee type.';

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!validateForm()) return;

    setSaving(true);
    setError('');

    const payload = {
      faculty_id: form.faculty_id.trim().toUpperCase(),
      department_id: Number(form.department_id),
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      email: form.email.trim().toLowerCase(),
      phone: form.phone.replace(/[\s()-]/g, ''),
      designation: form.designation,
      qualification: form.qualification.trim(),
      joining_date: form.joining_date,
      employee_type: form.employee_type,
      is_active: form.is_active,
    };

    try {
      if (editingId) {
        await axios.put(`${FACULTY_API_URL}/${editingId}`, payload, authHeaders);
        setNotice(`${payload.first_name} ${payload.last_name} was updated.`);
      } else {
        const response = await axios.post(FACULTY_API_URL, payload, authHeaders);
        if (response.data.generated_password) {
          setCredentials({
            name: response.data.full_name,
            email: response.data.email,
            password: response.data.generated_password,
          });
        }
        setNotice(`${response.data.full_name} was added to the faculty list.`);
      }
      closeModal();
      fetchFaculty();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Operation failed.');
    } finally {
      setSaving(false);
    }
  };

  // ------------------------------------------------------- row actions

  const handleToggleStatus = async (item) => {
    const nextStatus = !item.is_active;
    const verb = nextStatus ? 'activate' : 'deactivate';
    if (!window.confirm(`Are you sure you want to ${verb} ${item.full_name}?`)) return;

    setBusyRowId(item.id);
    try {
      await axios.patch(`${FACULTY_API_URL}/${item.id}/status`, { is_active: nextStatus }, authHeaders);
      setNotice(`${item.full_name} is now ${nextStatus ? 'active' : 'inactive'}.`);
      fetchFaculty();
    } catch (err) {
      setError(err?.response?.data?.detail || `Could not ${verb} this faculty member.`);
    } finally {
      setBusyRowId(null);
    }
  };

  const handleResetPassword = async (item) => {
    if (!window.confirm(`Generate a new password for ${item.full_name}? Their current password stops working.`)) return;

    setBusyRowId(item.id);
    try {
      const response = await axios.post(`${FACULTY_API_URL}/${item.id}/reset-password`, {}, authHeaders);
      setCredentials({
        name: response.data.full_name,
        email: response.data.email,
        password: response.data.generated_password,
      });
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not reset the password.');
    } finally {
      setBusyRowId(null);
    }
  };

  const handleDelete = async (item) => {
    const confirmed = window.confirm(
      `Delete ${item.full_name} permanently?\n\nThis also removes their login account. To keep their history, deactivate them instead.`,
    );
    if (!confirmed) return;

    setBusyRowId(item.id);
    try {
      await axios.delete(`${FACULTY_API_URL}/${item.id}`, authHeaders);
      setNotice(`${item.full_name} was deleted.`);
      fetchFaculty();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not delete this faculty member.');
    } finally {
      setBusyRowId(null);
    }
  };

  const copyCredentials = async () => {
    if (!credentials) return;
    const text = `Email: ${credentials.email}\nPassword: ${credentials.password}`;
    try {
      await navigator.clipboard.writeText(text);
      setNotice('Credentials copied to the clipboard.');
    } catch {
      setError('Could not copy automatically — please copy the credentials manually.');
    }
  };

  const resetFilters = () => {
    setFilters(emptyFilters);
    setSearch('');
  };

  // ------------------------------------------------------------ render

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar page-topbar">
          <div className="welcome-text">
            <strong>Faculty Management</strong>
            <span className="page-subtitle">Create accounts, manage designations, and control login access.</span>
          </div>

          <div className="topbar-right">
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Add Faculty
            </button>
          </div>
        </header>

        <section className="mini-stats">
          <div className="mini-stat">
            <span className="mini-stat-label">Total Faculty</span>
            <strong className="mini-stat-value">{stats.total}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Active</span>
            <strong className="mini-stat-value tone-green">{stats.active}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Inactive</span>
            <strong className="mini-stat-value tone-gray">{stats.inactive}</strong>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-label">Departments Covered</span>
            <strong className="mini-stat-value tone-blue">{stats.departmentsCovered}</strong>
          </div>
        </section>

        <div className="filter-bar">
          <input
            className="department-search filter-search"
            type="search"
            placeholder="Search by name, faculty ID, email, phone, or qualification..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <select
            className="department-search"
            value={filters.department_id}
            onChange={(e) => setFilters((current) => ({ ...current, department_id: e.target.value }))}
          >
            <option value="">All Departments</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name} ({department.code})
              </option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.designation}
            onChange={(e) => setFilters((current) => ({ ...current, designation: e.target.value }))}
          >
            <option value="">All Designations</option>
            {designations.map((designation) => (
              <option key={designation} value={designation}>{designation}</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.employee_type}
            onChange={(e) => setFilters((current) => ({ ...current, employee_type: e.target.value }))}
          >
            <option value="">All Employee Types</option>
            {employeeTypes.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>

          <select
            className="department-search"
            value={filters.status}
            onChange={(e) => setFilters((current) => ({ ...current, status: e.target.value }))}
          >
            <option value="">All Statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
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
          <div className="error-box dismissable" onClick={() => setError('')} role="alert">
            {error}
          </div>
        )}
        {notice && (
          <div className="success-box dismissable" onClick={() => setNotice('')} role="status">
            {notice}
          </div>
        )}

        <div className="department-table-wrap scroll-table">
          <table className="department-table faculty-table">
            <thead>
              <tr>
                <th className="sortable" onClick={() => toggleSort('faculty_id')}>ID{sortIndicator('faculty_id')}</th>
                <th className="sortable" onClick={() => toggleSort('name')}>Name{sortIndicator('name')}</th>
                <th className="sortable" onClick={() => toggleSort('department_name')}>Department{sortIndicator('department_name')}</th>
                <th className="sortable" onClick={() => toggleSort('designation')}>Designation{sortIndicator('designation')}</th>
                <th className="sortable" onClick={() => toggleSort('employee_type')}>Type{sortIndicator('employee_type')}</th>
                <th className="sortable" onClick={() => toggleSort('joining_date')}>Joined{sortIndicator('joining_date')}</th>
                <th className="sortable" onClick={() => toggleSort('is_active')}>Status{sortIndicator('is_active')}</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="8" className="table-loading">Loading faculty...</td>
                </tr>
              ) : visibleFaculty.length === 0 ? (
                <tr>
                  <td colSpan="8" className="table-empty">
                    {activeFilterCount
                      ? 'No faculty match the current filters.'
                      : 'No faculty yet. Use “+ Add Faculty” to create the first account.'}
                  </td>
                </tr>
              ) : (
                visibleFaculty.map((item) => (
                  <tr key={item.id} className={item.is_active ? '' : 'row-inactive'}>
                    <td className="mono">{item.faculty_id}</td>
                    <td>
                      <button type="button" className="link-btn dept-name" onClick={() => setDetailsFor(item)}>
                        {item.full_name}
                      </button>
                      <div className="dept-desc">{item.email}</div>
                    </td>
                    <td>
                      <div>{item.department_code || '—'}</div>
                      <div className="dept-desc">{item.department_name || ''}</div>
                    </td>
                    <td>{item.designation}</td>
                    <td>{item.employee_type}</td>
                    <td>{formatDate(item.joining_date)}</td>
                    <td>
                      <span className={`status-badge ${item.is_active ? 'active' : 'inactive'}`}>
                        {item.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button type="button" className="table-btn view-btn" onClick={() => setDetailsFor(item)}>View</button>
                        <button type="button" className="table-btn edit-btn" onClick={() => openEditModal(item)}>Edit</button>
                        <button
                          type="button"
                          className={`table-btn ${item.is_active ? 'warn-btn' : 'success-btn'}`}
                          onClick={() => handleToggleStatus(item)}
                          disabled={busyRowId === item.id}
                        >
                          {item.is_active ? 'Deactivate' : 'Activate'}
                        </button>
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

        {!loading && sortedFaculty.length > 0 && (
          <div className="table-footer">
            <span>
              Showing {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, sortedFaculty.length)} of{' '}
              {sortedFaculty.length}
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

      {/* ---------------------------------------------------- add / edit */}
      {modalOpen && (
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal-card wide" onClick={(e) => e.stopPropagation()}>
            <h3>{editingId ? 'Edit Faculty' : 'Add Faculty'}</h3>
            <p className="modal-hint">
              {editingId
                ? 'Changes to the email address update the linked login account.'
                : 'A login account is created automatically and a password is generated for you to hand over.'}
            </p>

            <form onSubmit={handleSubmit} className="department-form form-grid">
              <label>
                Faculty ID
                <input type="text" value={form.faculty_id} onChange={setField('faculty_id')} placeholder="FAC001" />
                {formErrors.faculty_id && <span className="field-error">{formErrors.faculty_id}</span>}
              </label>

              <label>
                Department
                <select value={form.department_id} onChange={setField('department_id')} disabled={!departments.length}>
                  <option value="">{departments.length ? 'Select department' : 'No departments available'}</option>
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name} ({department.code})
                    </option>
                  ))}
                </select>
                {formErrors.department_id && <span className="field-error">{formErrors.department_id}</span>}
              </label>

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
                Email
                <input type="email" value={form.email} onChange={setField('email')} placeholder="rahul@college.edu" />
                {formErrors.email && <span className="field-error">{formErrors.email}</span>}
              </label>

              <label>
                Phone
                <input type="tel" value={form.phone} onChange={setField('phone')} placeholder="9876543210" />
                {formErrors.phone && <span className="field-error">{formErrors.phone}</span>}
              </label>

              <label>
                Designation
                <select value={form.designation} onChange={setField('designation')}>
                  <option value="">Select designation</option>
                  {designations.map((designation) => (
                    <option key={designation} value={designation}>{designation}</option>
                  ))}
                </select>
                {formErrors.designation && <span className="field-error">{formErrors.designation}</span>}
              </label>

              <label>
                Employee Type
                <select value={form.employee_type} onChange={setField('employee_type')}>
                  <option value="">Select employee type</option>
                  {employeeTypes.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
                {formErrors.employee_type && <span className="field-error">{formErrors.employee_type}</span>}
              </label>

              <label>
                Qualification
                <input type="text" value={form.qualification} onChange={setField('qualification')} placeholder="M.Tech / Ph.D" />
                {formErrors.qualification && <span className="field-error">{formErrors.qualification}</span>}
              </label>

              <label>
                Joining Date
                <input type="date" value={form.joining_date} onChange={setField('joining_date')} />
                {formErrors.joining_date && <span className="field-error">{formErrors.joining_date}</span>}
              </label>

              <label className="checkbox-row span-2">
                <input type="checkbox" checked={form.is_active} onChange={setField('is_active')} />
                <span>Active — an inactive faculty member cannot sign in.</span>
              </label>

              <div className="modal-actions span-2">
                <button type="button" className="secondary-btn" onClick={closeModal}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={saving}>
                  {saving ? 'Saving...' : editingId ? 'Update Faculty' : 'Create Faculty'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------- details */}
      {detailsFor && (
        <div className="modal-backdrop" onClick={() => setDetailsFor(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Faculty Profile</h3>

            <div className="profile-grid">
              <div><span>Faculty ID</span><strong className="mono">{detailsFor.faculty_id}</strong></div>
              <div><span>Name</span><strong>{detailsFor.full_name}</strong></div>
              <div><span>Email</span><strong>{detailsFor.email}</strong></div>
              <div><span>Phone</span><strong>{detailsFor.phone}</strong></div>
              <div><span>Department</span><strong>{detailsFor.department_name} ({detailsFor.department_code})</strong></div>
              <div><span>Designation</span><strong>{detailsFor.designation}</strong></div>
              <div><span>Qualification</span><strong>{detailsFor.qualification}</strong></div>
              <div><span>Employee Type</span><strong>{detailsFor.employee_type}</strong></div>
              <div><span>Joining Date</span><strong>{formatDate(detailsFor.joining_date)}</strong></div>
              <div>
                <span>Status</span>
                <strong>
                  <span className={`status-badge ${detailsFor.is_active ? 'active' : 'inactive'}`}>
                    {detailsFor.is_active ? 'Active' : 'Inactive'}
                  </span>
                </strong>
              </div>
            </div>

            <FacultyTeachingPanel facultyId={detailsFor.id} />

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
                Edit Faculty
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --------------------------------------------------- credentials */}
      {credentials && (
        <div className="modal-backdrop" onClick={() => setCredentials(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Login Credentials</h3>
            <p className="modal-hint">
              This password is shown once. Copy it now and share it with {credentials.name}.
            </p>

            <div className="credentials-box">
              <div><span>Email</span><strong className="mono">{credentials.email}</strong></div>
              <div><span>Password</span><strong className="mono">{credentials.password}</strong></div>
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
