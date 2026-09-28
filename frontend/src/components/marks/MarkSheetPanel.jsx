import MarkSheetTable from './MarkSheetTable';
import { STATUS_LABEL, TYPE_LABEL } from '../../services/assessmentService';

/**
 * The sheet, its header numbers, and the save control.
 *
 * "38 of 52 entered" stays visible while typing — it is the only way to know
 * whether a long sheet is finished without counting it by eye.
 */
export default function MarkSheetPanel({
  sheet,
  rows,
  dirty,
  saving,
  error,
  notice,
  onChange,
  onSave,
  onReset,
  onDismissError,
}) {
  if (!sheet) {
    return (
      <section className="panel-card">
        <p className="empty-note">Pick an assessment to open its mark sheet.</p>
      </section>
    );
  }

  const entered = rows.filter(
    (row) => row.is_absent || row.is_malpractice || (row.draft ?? '') !== '',
  ).length;
  const invalid = rows.some((row) => {
    const raw = row.draft ?? '';
    if (raw === '') return false;
    const value = Number(raw);
    return Number.isNaN(value) || value < 0 || value > sheet.max_marks;
  });

  return (
    <section className="panel-card mark-sheet-panel">
      <header className="panel-head">
        <div>
          <h3>{sheet.assessment_name}</h3>
          <span className="page-subtitle">
            {sheet.subject_code} · {sheet.subject_name} · {sheet.section_name} ·{' '}
            {TYPE_LABEL[sheet.assessment_type] || sheet.assessment_type} · out of {sheet.max_marks}
            {' '}· {sheet.weightage_percent}% of the subject
          </span>
        </div>
        <div className="panel-head-meta">
          <span className="status-badge">{STATUS_LABEL[sheet.status] || sheet.status}</span>
          <span className="entry-progress">
            {entered} of {sheet.total_students} entered
          </span>
        </div>
      </header>

      {sheet.locked_reason && (
        <div className="notice-box" role="status">{sheet.locked_reason}</div>
      )}
      {error && (
        <div className="error-box dismissable" onClick={onDismissError} role="alert">{error}</div>
      )}
      {notice && <div className="notice-box" role="status">{notice}</div>}

      <MarkSheetTable
        rows={rows}
        maxMarks={sheet.max_marks}
        passMarks={sheet.pass_marks}
        disabled={!sheet.editable || saving}
        onChange={onChange}
      />

      <div className="action-buttons sheet-actions">
        <button
          type="button"
          className="table-btn success-btn"
          onClick={onSave}
          disabled={!sheet.editable || saving || invalid || !dirty}
        >
          {saving ? 'Saving…' : 'Save marks'}
        </button>
        <button type="button" className="table-btn" onClick={onReset} disabled={saving || !dirty}>
          Discard changes
        </button>
        {invalid && <span className="field-error">Some marks are out of range.</span>}
        {dirty && !invalid && <span className="page-subtitle">Unsaved changes.</span>}
      </div>

      <dl className="sheet-summary">
        <div><dt>Average</dt><dd>{sheet.average_marks} ({sheet.average_percent}%)</dd></div>
        <div><dt>Highest</dt><dd>{sheet.highest_marks ?? '—'}</dd></div>
        <div><dt>Lowest</dt><dd>{sheet.lowest_marks ?? '—'}</dd></div>
        <div><dt>Passed</dt><dd>{sheet.pass_count}</dd></div>
        <div><dt>Failed</dt><dd>{sheet.fail_count}</dd></div>
        <div><dt>Absent</dt><dd>{sheet.absent_count}</dd></div>
        <div><dt>Not entered</dt><dd>{sheet.pending_count}</dd></div>
      </dl>
    </section>
  );
}
