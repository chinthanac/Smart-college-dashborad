import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AdminSidebar from '../components/AdminSidebar';

const API_URL = 'http://localhost:8000/api/academic-years';

const emptyForm = {
  name: '',
  start_date: '',
  end_date: '',
  is_current: true,
};

export default function AcademicYearsPage() {
  const navigate = useNavigate();
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

  const fetchAcademicYears = async () => {
    if (!token) {
      navigate('/login');
      return;
    }

    try {
      const response = await axios.get(API_URL, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setAcademicYears(response.data);
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load academic years.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAcademicYears();
  }, []);

  const filteredAcademicYears = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return academicYears;

    return academicYears.filter((item) => item.name.toLowerCase().includes(query));
  }, [academicYears, search]);

  const openCreateModal = () => {
    setEditingId(null);
    setForm(emptyForm);
    setModalOpen(true);
    setError('');
  };

  const openEditModal = (item) => {
    setEditingId(item.id);
    setForm({
      name: item.name,
      start_date: item.start_date,
      end_date: item.end_date,
      is_current: item.is_current,
    });
    setModalOpen(true);
    setError('');
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setForm(emptyForm);
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit',
      month: 'short',
      year: '2-digit',
    }).format(date);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError('Academic year name is required.');
      return;
    }

    if (!form.start_date || !form.end_date) {
      setError('Start date and end date are required.');
      return;
    }

    if (new Date(form.end_date) <= new Date(form.start_date)) {
      setError('End date must be after the start date.');
      return;
    }

    setSaving(true);
    setError('');

    try {
      const payload = {
        name: form.name.trim(),
        start_date: form.start_date,
        end_date: form.end_date,
        is_current: form.is_current,
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
      fetchAcademicYears();
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Operation failed.';
      setError(detail);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    const confirmed = window.confirm('Are you sure you want to delete this academic year?');
    if (!confirmed) return;

    try {
      await axios.delete(`${API_URL}/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchAcademicYears();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not delete academic year.');
    }
  };

  const handleSetCurrent = async (id) => {
    try {
      await axios.patch(`${API_URL}/${id}/set-current`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchAcademicYears();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not set the current academic year.');
    }
  };

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <main className="content-panel department-page">
        <header className="topbar" style={{ paddingBottom: '12px' }}>
          <div className="welcome-text">
            <strong>Academic Years</strong>
          </div>

          <div className="topbar-right">
            <button type="button" className="primary-btn department-primary-btn" onClick={openCreateModal}>
              + Add Year
            </button>
          </div>
        </header>

        <div className="department-toolbar">
          <input
            className="department-search"
            type="text"
            placeholder="Search academic years..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="department-table-wrap">
          <table className="department-table">
            <thead>
              <tr>
                <th>Year</th>
                <th>Start</th>
                <th>End</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="5" className="table-loading">Loading academic years...</td>
                </tr>
              ) : filteredAcademicYears.length === 0 ? (
                <tr>
                  <td colSpan="5" className="table-empty">No academic years found.</td>
                </tr>
              ) : (
                filteredAcademicYears.map((item) => (
                  <tr key={item.id}>
                    <td>{item.name}</td>
                    <td>{formatDate(item.start_date)}</td>
                    <td>{formatDate(item.end_date)}</td>
                    <td>
                      <span className={`status-badge ${item.is_current ? 'active' : item.is_active ? 'inactive' : 'inactive'}`}>
                        {item.is_current ? '● Current' : item.is_active ? 'Inactive' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        {!item.is_current && (
                          <button type="button" className="table-btn edit-btn" onClick={() => handleSetCurrent(item.id)}>
                            Set Current
                          </button>
                        )}
                        <button type="button" className="table-btn edit-btn" onClick={() => openEditModal(item)}>
                          Edit
                        </button>
                        <button type="button" className="table-btn delete-btn" onClick={() => handleDelete(item.id)}>
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
            <h3>{editingId ? 'Edit Academic Year' : 'Create Academic Year'}</h3>
            <form onSubmit={handleSubmit} className="department-form">
              <label>
                Academic Year
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="2026-27"
                />
              </label>

              <label>
                Start Date
                <input
                  type="date"
                  value={form.start_date}
                  onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                />
              </label>

              <label>
                End Date
                <input
                  type="date"
                  value={form.end_date}
                  onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                />
              </label>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={form.is_current}
                  onChange={(e) => setForm({ ...form, is_current: e.target.checked })}
                />
                <span>Set as Current</span>
              </label>

              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={closeModal}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={saving}>
                  {saving ? 'Saving...' : editingId ? 'Update Year' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
