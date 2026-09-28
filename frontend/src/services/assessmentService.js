import axios from 'axios';

const API = 'http://localhost:8000/api';
const ASSESSMENTS_URL = `${API}/assessments`;
const MARKS_URL = `${API}/marks`;
const RESULTS_URL = `${API}/results`;

const authHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('smart_college_token')}` },
});

const clean = (params) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));

// Reused rather than reimplemented — the 422 `detail` shape is the same here.
export { apiErrorMessage } from './timetableService';
export { formatDateValue, toDateValue } from './attendanceService';

export const ASSESSMENT_TYPES = [
  'INTERNAL',
  'ASSIGNMENT',
  'LAB',
  'QUIZ',
  'MODEL',
  'EXTERNAL',
];

export const TYPE_LABEL = {
  INTERNAL: 'Internal',
  ASSIGNMENT: 'Assignment',
  LAB: 'Lab',
  QUIZ: 'Quiz',
  MODEL: 'Model',
  EXTERNAL: 'External',
};

export const ASSESSMENT_STATUSES = ['DRAFT', 'PUBLISHED', 'LOCKED'];

export const STATUS_LABEL = {
  DRAFT: 'Draft',
  PUBLISHED: 'Published',
  LOCKED: 'Locked',
};

// Draft is deliberately the muted chip: it reaches nobody, and the screen
// should say so at a glance.
export const STATUS_CLASS = {
  DRAFT: 'inactive',
  PUBLISHED: 'active',
  LOCKED: 'type-cross-dept',
};

export const ROW_STATE_LABEL = {
  PENDING: 'Not entered',
  ENTERED: 'Entered',
  ABSENT: 'Absent',
  MALPRACTICE: 'Malpractice',
};

export const MAX_TOTAL_WEIGHTAGE = 100;

/** Blank rather than 0 — a mark nobody has entered is not a zero. */
export const markValue = (row) =>
  row.marks_obtained === null || row.marks_obtained === undefined
    ? ''
    : String(row.marks_obtained);

/** "—" for anything unknown, so no screen ever prints a placeholder zero. */
export const showNumber = (value, suffix = '') =>
  value === null || value === undefined ? '—' : `${value}${suffix}`;

export const gradeTone = (letter) => {
  if (!letter) return 'muted';
  if (letter === 'F') return 'danger';
  if (letter === 'P' || letter === 'C') return 'warn';
  return 'good';
};

const assessmentService = {
  async options() {
    const { data } = await axios.get(`${ASSESSMENTS_URL}/options`, authHeaders());
    return data;
  },

  async list(params = {}) {
    const { data } = await axios.get(ASSESSMENTS_URL, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  async mine(params = {}) {
    const { data } = await axios.get(`${ASSESSMENTS_URL}/me`, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  async get(id) {
    const { data } = await axios.get(`${ASSESSMENTS_URL}/${id}`, authHeaders());
    return data;
  },

  /** What is left of a class's 100%, and what has taken the rest. */
  async budget(teachingAssignmentId, excludeId = null) {
    const { data } = await axios.get(`${ASSESSMENTS_URL}/budget`, {
      ...authHeaders(),
      params: clean({
        teaching_assignment_id: teachingAssignmentId,
        exclude_id: excludeId,
      }),
    });
    return data;
  },

  async create(payload) {
    const { data } = await axios.post(ASSESSMENTS_URL, payload, authHeaders());
    return data;
  },

  async update(id, payload) {
    const { data } = await axios.patch(`${ASSESSMENTS_URL}/${id}`, payload, authHeaders());
    return data;
  },

  /** action: publish | lock | unlock */
  async setStatus(id, action, reason = null) {
    const { data } = await axios.patch(
      `${ASSESSMENTS_URL}/${id}/status`,
      { action, reason },
      authHeaders(),
    );
    return data;
  },

  async remove(id, force = false) {
    await axios.delete(`${ASSESSMENTS_URL}/${id}`, {
      ...authHeaders(),
      params: force ? { force: true } : {},
    });
  },

  // --- marks ---

  /** Read-only. Opening a sheet never writes anything. */
  async sheet(assessmentId) {
    const { data } = await axios.get(`${MARKS_URL}/sheet`, {
      ...authHeaders(),
      params: { assessment_id: assessmentId },
    });
    return data;
  },

  async saveSheet(assessmentId, entries) {
    const { data } = await axios.post(
      `${MARKS_URL}/sheet`,
      { assessment_id: assessmentId, entries },
      authHeaders(),
    );
    return data;
  },

  async myAssessments(params = {}) {
    const { data } = await axios.get(`${MARKS_URL}/my-assessments`, {
      ...authHeaders(),
      params: clean(params),
    });
    return data;
  },

  // --- results ---

  async myResult() {
    const { data } = await axios.get(`${RESULTS_URL}/me`, authHeaders());
    return data;
  },

  async studentResult(studentId) {
    const { data } = await axios.get(`${RESULTS_URL}/student`, {
      ...authHeaders(),
      params: { student_id: studentId },
    });
    return data;
  },

  async subjectReport(sectionId, subjectId) {
    const { data } = await axios.get(`${RESULTS_URL}/subject`, {
      ...authHeaders(),
      params: { section_id: sectionId, subject_id: subjectId },
    });
    return data;
  },

  async sectionReport(sectionId) {
    const { data } = await axios.get(`${RESULTS_URL}/section`, {
      ...authHeaders(),
      params: { section_id: sectionId },
    });
    return data;
  },

  // --- the academic chain, shared with the attendance filters ---
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

  /** The classes an assessment can hang off. */
  async teachingAssignments(params = {}) {
    const { data } = await axios.get(`${API}/teaching-assignments`, {
      ...authHeaders(),
      params: clean({ is_active: true, ...params }),
    });
    return data;
  },
};

export default assessmentService;
