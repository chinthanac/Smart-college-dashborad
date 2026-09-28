import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api/auth';

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${API_URL}/login`, form);
      localStorage.setItem('smart_college_token', response.data.access_token);
      localStorage.setItem('smart_college_user', JSON.stringify(response.data.user));
      const { role } = response.data.user;
      navigate(
        role === 'FACULTY' ? '/faculty/dashboard'
          : role === 'STUDENT' ? '/student/dashboard'
            : '/admin/dashboard',
      );
    } catch (err) {
      const message = err?.response?.data?.detail || 'Invalid email or password';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <div className="auth-card">
        <h1>Smart College</h1>
        <p className="subtitle">Sign in as Admin or Faculty</p>

        {error && <div className="error-box">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="admin@smartcollege.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="Enter password"
              required
            />
          </div>

          <button className="primary-btn" disabled={loading} type="submit">
            {loading ? 'Signing in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
}
