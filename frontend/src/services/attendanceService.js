import axios from 'axios';

const API = 'http://localhost:8000/api';
const ATTENDANCE_URL = `${API}/attendance`;

const authHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('smart_college_token')}` },
});

const clean = (params) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));

// Reused rather than reimplemented — the 422 `detail` shape is the same here.
export { apiErrorMessage, DAY_NAMES, SHORT_DAY_NAMES, todayIndex } from './timetableService';

export const ATTENDANCE_STATUSES = ['PRESENT', 'ABSENT', 'LATE', 'EXCUSED'];
export const PRESENT_STATUSES = ['PRESENT', 'LATE'];

export const STATUS_LABEL = {
  PRESENT: 'Present',
  ABSENT: 'Absent',
  LATE: 'Late',
  EXCUSED: 'Excused',
};

// Maps the API's four standings onto the coverage-chip colours the timetable
// already ships, so no new CSS is needed for the report.
export const STANDING_CLASS = {
  GOOD: 'COMPLETE',
  AT_RISK: 'UNDER_SCHEDULED',
  NO_DATA: 'UNSCHEDULED',
  SHORT: 'OVER_SCHEDULED',
};

export const STANDING_LABEL = {
  GOOD: 'Good',
  AT_RISK: 'At risk',
  NO_DATA: 'No data',
  SHORT: 'Short',
};

/**
 * Local calendar date as YYYY-MM-DD.
 *
 * NOT toISOString(), which converts to UTC first: in a negative-offset zone an
 * evening click would send tomorrow's date (rejected as "has not happened
 * yet"), and in a positive-offset one an early-morning click would send
 * yesterday's (rejected for the wrong weekday).
 */
export const toDateValue = (value = new Date()) => {
  const d = value instanceof Date ? value : new Date(value);
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0'),
  ].join('-');
};

/**
 * Weekday of a "YYYY-MM-DD" string in the API's 0=Monday convention.
 * Built with new Date(y, m-1, d) — new Date("2026-09-24") is UTC midnight and
 * can land on the previous day once getDay() applies the local offset.
 */
export const weekdayOf = (value) => {
  if (!value) return null;
  const [y, m, d] = String(value).split('-').map(Number);
  if (!y || !m || !d) return null;
  return (new Date(y, m - 1, d).getDay() + 6) % 7;
};

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

const attendanceService = {
  async options() {
    const { data } = await axios.get(`${ATTENDANCE_URL}/options`);
    return data;
  },

  /** The signed-in lecturer's classes on one date, and which are marked. */
  async myClasses(classDate) {
    const { data } = await axios.get(`${ATTENDANCE_URL}/my-classes`, {
      ...authHeaders(),
      params: clean({ class_date: classDate }),
    });
    return data;
  },

  /** Read-only — opening a sheet never creates a session. */
  async sheet(timetableEntryId, classDate) {
    const { data } = await axios.get(`${ATTENDANCE_URL}/sheet`, {
      ...authHeaders(),
      params: { timetable_entry_id: timetableEntryId, class_date: classDate },
    });
    return data;
  },

  async saveSheet(payload) {
    const { data } = await axios.post(`${ATTENDANCE_URL}/sheet`, payload, authHeaders());
    return data;
  },

  async sessions(params = {}) {
    const { data } = await axios.get(`${ATTENDANCE_URL}/sessions`, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  async session(id) {
    const { data } = await axios.get(`${ATTENDANCE_URL}/sessions/${id}`, authHeaders());
    return data;
  },

  async setSessionStatus(id, sessionStatus, cancelReason = null) {
    const { data } = await axios.patch(
      `${ATTENDANCE_URL}/sessions/${id}/status`,
      { session_status: sessionStatus, cancel_reason: cancelReason },
      authHeaders(),
    );
    return data;
  },

  async removeSession(id) {
    await axios.delete(`${ATTENDANCE_URL}/sessions/${id}`, authHeaders());
  },

  async sectionReport(params = {}) {
    const { data } = await axios.get(`${ATTENDANCE_URL}/report/section`, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  async studentReport(params = {}) {
    const { data } = await axios.get(`${ATTENDANCE_URL}/report/student`, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  /** The signed-in student's own record. */
  async mine(params = {}) {
    const { data } = await axios.get(`${ATTENDANCE_URL}/me`, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  // --- the academic chain, shared with the timetable filters ---
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

  async subjects(semesterId) {
    if (!semesterId) return [];
    const { data } = await axios.get(`${API}/subjects`, {
      ...authHeaders(),
      params: { semester_id: semesterId, is_active: true },
    });
    return data;
  },
};

export default attendanceService;
