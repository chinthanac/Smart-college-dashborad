import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminSidebar from '../components/AdminSidebar';

const API_URL = 'http://localhost:8000/api/departments';

const emptyForm = {
  name: '',
  code: '',
  description: '',
};

export default function DepartmentsPage() {
  const navigate = useNavigate();
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
      return;
    }

    try {
      const response = await axios.get(API_URL, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDepartments(response.data);
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load departments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDepartments();
  }, []);

  const filteredDepartments = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return departments;

    return departments.filter((department) => {
      return (
        department.name.toLowerCase().includes(query) ||
        department.code.toLowerCase().includes(query)
      );
    });
  }, [departments, search]);

  const openCreateModal = () => {
    setEditingId(null);
    setForm(emptyForm);
    setModalOpen(true);
    setError('');
  };

  const openEditModal = (department) => {
    setEditingId(department.id);
    setForm({
      name: department.name,
      code: department.code,
      description: department.description || '',
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
    if (!form.name || !form.code) {
      setError('Department name and code are required.');
      return;
    }

    setSaving(true);
    setError('');

    try {
      const payload = {
        name: form.name,
        code: form.code,
        description: form.description,
      };

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
      fetchDepartments();
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Operation failed.';
      setError(detail);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (departmentId) => {
    const confirmed = window.confirm('Are you sure you want to delete this department?');
    if (!confirmed) return;

    try {
      await axios.delete(`${API_URL}/${departmentId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchDepartments();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not delete department.');
    }
  };

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar" style={{ paddingBottom: '12px' }}>
          <div className="welcome-text">
            <strong>Departments</strong>
          </div>

          <div className="topbar-right">
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Add Department
            </button>
          </div>
        </header>

        <div className="department-toolbar">
          <input
            className="department-search"
            type="text"
            placeholder="Search departments..."
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
                <th>Department</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="4" className="table-loading">Loading departments...</td>
                </tr>
              ) : filteredDepartments.length === 0 ? (
                <tr>
                  <td colSpan="4" className="table-empty">No departments found.</td>
                </tr>
              ) : (
                filteredDepartments.map((department) => (
                  <tr key={department.id}>
                    <td>{department.code}</td>
                    <td>
                      <div className="dept-name">{department.name}</div>
                      <div className="dept-desc">{department.description || 'No description provided'}</div>
                    </td>
                    <td>
                      <span className={`status-badge ${department.is_active ? 'active' : 'inactive'}`}>
                        {department.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button type="button" className="table-btn edit-btn" onClick={() => openEditModal(department)}>
                          Edit
                        </button>
                        <button type="button" className="table-btn delete-btn" onClick={() => handleDelete(department.id)}>
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
            <h3>{editingId ? 'Edit Department' : 'Add Department'}</h3>
            <form onSubmit={handleSubmit} className="department-form">
              <label>
                Department Name
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Computer Science and Engineering"
                />
              </label>

              <label>
                Department Code
                <input
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="CSE"
                />
              </label>

              <label>
                Description
                <textarea
                  rows="4"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Department description"
                />
              </label>

              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={closeModal}>
                  Cancel
                </button>
                <button type="submit" className="primary-btn" disabled={saving}>
                  {saving ? 'Saving...' : editingId ? 'Update Department' : 'Create Department'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
