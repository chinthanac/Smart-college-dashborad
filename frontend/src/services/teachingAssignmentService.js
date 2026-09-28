import axios from 'axios';

const API = 'http://localhost:8000/api';
const ASSIGNMENTS_URL = `${API}/teaching-assignments`;

const authHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('smart_college_token')}` },
});

const clean = (params) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));

const teachingAssignmentService = {
  async list(params = {}) {
    const { data } = await axios.get(ASSIGNMENTS_URL, { ...authHeaders(), params: clean(params) });
    return data;
  },

  async get(id) {
    const { data } = await axios.get(`${ASSIGNMENTS_URL}/${id}`, authHeaders());
    return data;
  },

  async create(payload) {
    const { data } = await axios.post(ASSIGNMENTS_URL, payload, authHeaders());
    return data;
  },

  async update(id, payload) {
    const { data } = await axios.put(`${ASSIGNMENTS_URL}/${id}`, payload, authHeaders());
    return data;
  },

  async bulkAssign(payload) {
    const { data } = await axios.post(`${ASSIGNMENTS_URL}/bulk`, payload, authHeaders());
    return data;
  },

  async setStatus(id, isActive) {
    const { data } = await axios.patch(
      `${ASSIGNMENTS_URL}/${id}/status`,
      { is_active: isActive },
      authHeaders(),
    );
    return data;
  },

  async remove(id) {
    await axios.delete(`${ASSIGNMENTS_URL}/${id}`, authHeaders());
  },

  /** Everything the signed-in faculty member teaches. */
  async mine(params = {}) {
    const { data } = await axios.get(`${ASSIGNMENTS_URL}/me`, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  // --- the dependent Department → Course → Semester → {Subject, Section} chain ---
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

  /** Subjects and sections both come from the SAME semester, which is what
   *  makes an invalid subject/section pair unreachable from the UI. */
  async subjects(semesterId) {
    if (!semesterId) return [];
    const { data } = await axios.get(`${API}/subjects`, {
      ...authHeaders(),
      params: { semester_id: semesterId, is_active: true },
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

  async faculty() {
    const { data } = await axios.get(`${API}/faculty`, {
      ...authHeaders(),
      params: { is_active: true },
    });
    return data;
  },
};

export default teachingAssignmentService;
