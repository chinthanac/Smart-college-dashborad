import axios from 'axios';

const API = 'http://localhost:8000/api';

const authHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('smart_college_token')}` },
});

// Reused, not reimplemented — the 422 `detail` shape is the same everywhere.
export { apiErrorMessage } from './timetableService';

/** "24 Sep 2026" from a plain date string, without touching timezones. */
export const formatDateValue = (value) => {
  if (!value) return '—';
  const [y, m, d] = String(value).split('-').map(Number);
  if (!y || !m || !d) return value;
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
};

/** A timestamp, for "figures as of ...". */
export const formatMoment = (value) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const statsService = {
  async dashboard() {
    const { data } = await axios.get(`${API}/stats/dashboard`, authHeaders());
    return data;
  },
};

export default statsService;
