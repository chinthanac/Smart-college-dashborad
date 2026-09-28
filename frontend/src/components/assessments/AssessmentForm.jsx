import { useEffect, useState } from 'react';
import WeightageBar from './WeightageBar';
import assessmentService, {
  ASSESSMENT_TYPES,
  TYPE_LABEL,
  apiErrorMessage,
} from '../../services/assessmentService';

const blank = {
  teaching_assignment_id: '',
  assessment_type: 'INTERNAL',
  name: '',
  sequence_no: 1,
  description: '',
  max_marks: 50,
  weightage_percent: 30,
  pass_marks: '',
  scheduled_date: '',
  duration_minutes: '',
};

/**
 * Create or edit one component.
 *
 * The class cannot be changed on an edit: moving an assessment to another
 * class would strand the marks already entered against a roster that never
 * sat it, which is a delete and a create, not an edit.
 */
export default function AssessmentForm({ editing, assignments, onClose, onSaved }) {
  const [form, setForm] = useState(blank);
  const [budget, setBudget] = useState(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (editing) {
      setForm({
        teaching_assignment_id: String(editing.teaching_assignment_id),
        assessment_type: editing.assessment_type,
        name: editing.name,
        sequence_no: editing.sequence_no,
        description: editing.description || '',
        max_marks: editing.max_marks,
        weightage_percent: editing.weightage_percent,
        pass_marks: editing.pass_marks ?? '',
        scheduled_date: editing.scheduled_date || '',
        duration_minutes: editing.duration_minutes ?? '',
      });
    } else {
      setForm(blank);
    }
  }, [editing]);

  const assignmentId = form.teaching_assignment_id;

  useEffect(() => {
    if (!assignmentId) {
      setBudget(null);
      return undefined;
    }
    let live = true;
    assessmentService
      .budget(assignmentId, editing?.id ?? null)
      .then((data) => live && setBudget(data))
      .catch(() => live && setBudget(null));
    return () => { live = false; };
  }, [assignmentId, editing]);

  const set = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');

    const payload = {
      assessment_type: form.assessment_type,
      name: form.name.trim(),
      sequence_no: Number(form.sequence_no) || 1,
      description: form.description.trim() || null,
      max_marks: Number(form.max_marks),
      weightage_percent: Number(form.weightage_percent),
      pass_marks: form.pass_marks === '' ? null : Number(form.pass_marks),
      scheduled_date: form.scheduled_date || null,
      duration_minutes: form.duration_minutes === '' ? null : Number(form.duration_minutes),
    };

    try {
      const saved = editing
        ? await assessmentService.update(editing.id, payload)
        : await assessmentService.create({
            ...payload,
            teaching_assignment_id: Number(form.teaching_assignment_id),
          });
      onSaved(saved, editing ? 'Assessment updated.' : 'Assessment created.');
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save this assessment.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card wide" onClick={(event) => event.stopPropagation()}>
        <header className="modal-head">
          <h3>{editing ? 'Edit assessment' : 'New assessment'}</h3>
          <button type="button" className="table-btn" onClick={onClose}>Close</button>
        </header>

        {error && <div className="error-box" role="alert">{error}</div>}

        <form className="modal-form" onSubmit={handleSubmit}>
          <label>
            Class
            <select
              value={form.teaching_assignment_id}
              onChange={set('teaching_assignment_id')}
              disabled={Boolean(editing)}
              required
            >
              <option value="">Select a teaching assignment…</option>
              {assignments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.subject_code} · {item.section_name} · {item.faculty_name}
                </option>
              ))}
            </select>
            {editing && (
              <span className="page-subtitle">
                The class cannot be changed — marks are already attached to this roster.
              </span>
            )}
          </label>

          <div className="form-row">
            <label>
              Type
              <select value={form.assessment_type} onChange={set('assessment_type')}>
                {ASSESSMENT_TYPES.map((type) => (
                  <option key={type} value={type}>{TYPE_LABEL[type]}</option>
                ))}
              </select>
            </label>

            <label>
              Number
              <input type="number" min="1" max="99" value={form.sequence_no} onChange={set('sequence_no')} />
            </label>
          </div>

          <label>
            Name
            <input value={form.name} onChange={set('name')} placeholder="Internal 1" required />
          </label>

          <div className="form-row">
            <label>
              Out of
              <input type="number" min="1" step="0.5" value={form.max_marks} onChange={set('max_marks')} required />
            </label>

            <label>
              Pass mark
              <input
                type="number"
                min="0"
                step="0.5"
                value={form.pass_marks}
                onChange={set('pass_marks')}
                placeholder="40% of the maximum"
              />
            </label>

            <label>
              Weightage %
              <input
                type="number"
                min="0.5"
                max="100"
                step="0.5"
                value={form.weightage_percent}
                onChange={set('weightage_percent')}
                required
              />
            </label>
          </div>

          <WeightageBar
            budget={budget}
            pending={form.weightage_percent}
            excludeId={editing?.id ?? null}
          />

          <div className="form-row">
            <label>
              Scheduled for
              <input type="date" value={form.scheduled_date} onChange={set('scheduled_date')} />
            </label>

            <label>
              Duration (minutes)
              <input type="number" min="1" value={form.duration_minutes} onChange={set('duration_minutes')} />
            </label>
          </div>

          <label>
            Notes
            <textarea rows="2" value={form.description} onChange={set('description')} />
          </label>

          <div className="action-buttons">
            <button type="submit" className="table-btn success-btn" disabled={saving}>
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Create assessment'}
            </button>
            <button type="button" className="table-btn" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}
