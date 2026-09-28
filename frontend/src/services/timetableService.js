import axios from 'axios';

const API = 'http://localhost:8000/api';
const TIMETABLE_URL = `${API}/timetable`;
const TIME_SLOTS_URL = `${API}/time-slots`;

const authHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('smart_college_token')}` },
});

const clean = (params) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));

// Mirrors DAY_NAMES in app/schemas/timetable.py: 0 = Monday ... 6 = Sunday,
// which is datetime.date.weekday(), NOT JavaScript's Date.getDay().
export const DAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];

export const SHORT_DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// == DEFAULT_WORKING_DAYS. Sunday stays schedulable; this only decides what
// the grid shows before the admin asks for the weekend.
export const WORKING_DAYS = [0, 1, 2, 3, 4, 5];
export const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6];

/** JS Date.getDay() is 0=Sunday; the API is 0=Monday. */
export const todayIndex = () => (new Date().getDay() + 6) % 7;

/**
 * FastAPI's `detail` is a plain string for the 400/403/404/409s this module
 * raises, but a LIST of {loc, msg, type} dicts for a pydantic 422, and absent
 * entirely for a network failure. Rendering the list shape straight into JSX
 * throws "Objects are not valid as a React child" and blanks the page, so
 * every error message in this module goes through here first.
 */
export const apiErrorMessage = (err, fallback = 'Something went wrong.') => {
  const detail = err?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        const loc = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : '';
        return [loc, item?.msg].filter(Boolean).join(': ');
      })
      .filter(Boolean);
    return parts.length ? parts.join(' · ') : fallback;
  }

  if (detail && typeof detail === 'object') return detail.msg || fallback;
  if (err?.message === 'Network Error') {
    return 'Cannot reach the server. Is the API running on port 8000?';
  }
  return fallback;
};

const timetableService = {
  async list(params = {}) {
    const { data } = await axios.get(TIMETABLE_URL, { ...authHeaders(), params: clean(params) });
    return data;
  },

  /**
   * Every entry for one section, active AND inactive. A deactivated entry
   * still occupies its cell for clash purposes, so filtering it out here
   * would leave a cell that looks free but always 409s.
   */
  async forSection(sectionId) {
    return this.list({ section_id: sectionId });
  },

  async get(id) {
    const { data } = await axios.get(`${TIMETABLE_URL}/${id}`, authHeaders());
    return data;
  },

  async create(payload) {
    const { data } = await axios.post(TIMETABLE_URL, payload, authHeaders());
    return data;
  },

  async update(id, payload) {
    const { data } = await axios.put(`${TIMETABLE_URL}/${id}`, payload, authHeaders());
    return data;
  },

  async setStatus(id, isActive) {
    const { data } = await axios.patch(
      `${TIMETABLE_URL}/${id}/status`,
      { is_active: isActive },
      authHeaders(),
    );
    return data;
  },

  async remove(id) {
    await axios.delete(`${TIMETABLE_URL}/${id}`, authHeaders());
  },

  /**
   * The signed-in user's own week. Role-aware on the server: faculty get
   * everything they teach (including cross-department classes the scoped list
   * hides), students get their section's grid. Admins get a 400 — the admin
   * page must never call this.
   */
  async mine(params = {}) {
    const { data } = await axios.get(`${TIMETABLE_URL}/me`, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  async coverage(sectionId) {
    const { data } = await axios.get(`${TIMETABLE_URL}/coverage`, {
      ...authHeaders(),
      params: { section_id: sectionId },
    });
    return data;
  },

  async copyDay(payload) {
    const { data } = await axios.post(`${TIMETABLE_URL}/copy-day`, payload, authHeaders());
    return data;
  },

  /** Readable by every role — already ordered by period_number. */
  async timeSlots(isActive = true) {
    const { data } = await axios.get(TIME_SLOTS_URL, {
      ...authHeaders(),
      params: clean({ is_active: isActive }),
    });
    return data;
  },

  // --- the Department → Course → Semester → Section chain that scopes the grid ---
  async departments() {
    const { data } = await axios.get(`${API}/departments`, authHeaders());
    return data;
  },

  async courses(departmentId) {
    const params = departmentId ? { department_id: departmentId } : {};
    const { data } = await axios.get(`${API}/courses`, { ...authHeaders(), params });
    return data;
  },

  async semesters(courseId) {
    if (!courseId) return [];
    const { data } = await axios.get(`${API}/semesters`, {
      ...authHeaders(),
      params: { course_id: courseId },
    });
    return data;
  },

  async sections(semesterId) {
    if (!semesterId) return [];
    const { data } = await axios.get(`${API}/sections`, {
      ...authHeaders(),
      params: { semester_id: semesterId },
    });
    return data;
  },

  /**
   * What can be placed on this section's grid. Only ACTIVE assignments are
   * schedulable — resolve_assignment rejects a paused one with a 400.
   */
  async assignmentsForSection(sectionId) {
    if (!sectionId) return [];
    const { data } = await axios.get(`${API}/teaching-assignments`, {
      ...authHeaders(),
      params: { section_id: sectionId, is_active: true },
    });
    return data;
  },
};

export default timetableService;
