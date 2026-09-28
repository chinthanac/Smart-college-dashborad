import axios from 'axios';

const API = 'http://localhost:8000/api';
const SUBJECTS_URL = `${API}/subjects`;

const authHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('smart_college_token')}` },
});

/** All subject HTTP access lives here, so the components stay declarative. */
const subjectService = {
  async list(params = {}) {
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));
    const { data } = await axios.get(SUBJECTS_URL, { ...authHeaders(), params: clean });
    return data;
  },

  async get(id) {
    const { data } = await axios.get(`${SUBJECTS_URL}/${id}`, authHeaders());
    return data;
  },

  async create(payload) {
    const { data } = await axios.post(SUBJECTS_URL, payload, authHeaders());
    return data;
  },

  async update(id, payload) {
    const { data } = await axios.put(`${SUBJECTS_URL}/${id}`, payload, authHeaders());
    return data;
  },

  async setStatus(id, isActive) {
    const { data } = await axios.patch(`${SUBJECTS_URL}/${id}/status`, { is_active: isActive }, authHeaders());
    return data;
  },

  async remove(id) {
    await axios.delete(`${SUBJECTS_URL}/${id}`, authHeaders());
  },

  async options() {
    const { data } = await axios.get(`${SUBJECTS_URL}/options`, authHeaders());
    return data;
  },

  // --- the dependent Course → Semester chain ------------------------------
  async departments() {
    const { data } = await axios.get(`${API}/departments`, authHeaders());
    return data;
  },

  async courses(departmentId) {
    const params = departmentId ? { department_id: departmentId } : {};
    const { data } = await axios.get(`${API}/courses`, { ...authHeaders(), params });
    return data;
  },

  /** Only semesters belonging to the chosen course, per GET /api/semesters?course_id= */
  async semesters(courseId) {
    if (!courseId) return [];
    const { data } = await axios.get(`${API}/semesters`, { ...authHeaders(), params: { course_id: courseId } });
    return data;
  },
};

export default subjectService;
