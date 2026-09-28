import { useRef } from 'react';
import { ROW_STATE_LABEL, gradeTone } from '../../services/assessmentService';

/**
 * The roster, as a column of mark inputs.
 *
 * Marks entry is a hundred-keystroke task, so this is built for the keyboard
 * first: Enter and ArrowDown move to the next student, ArrowUp moves back,
 * and the cell is focused rather than the row. A value over the maximum flags
 * on the cell as it is typed, not on submit after ninety other entries.
 *
 * A blank input is "not entered", NOT zero — clearing one returns the student
 * to pending, and the API deletes their row.
 */
export default function MarkSheetTable({ rows, maxMarks, passMarks, disabled, onChange }) {
  const inputs = useRef([]);

  if (!rows.length) return <p className="empty-note">No students on this roster.</p>;

  const focusRow = (index) => {
    const next = inputs.current[index];
    if (next) {
      next.focus();
      next.select();
    }
  };

  const handleKeyDown = (event, index) => {
    if (event.key === 'Enter' || event.key === 'ArrowDown') {
      event.preventDefault();
      focusRow(index + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      focusRow(index - 1);
    }
  };

  return (
    <div className="department-table-wrap scroll-table">
      <table className="department-table mark-sheet">
        <thead>
          <tr>
            <th>Roll No</th>
            <th>Student</th>
            <th>Mark (of {maxMarks})</th>
            <th>Absent</th>
            <th>Malpractice</th>
            <th>Standing</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const raw = row.draft ?? '';
            const value = raw === '' ? null : Number(raw);
            const over = value !== null && value > maxMarks;
            const under = value !== null && value < 0;
            const invalid = over || under || (raw !== '' && Number.isNaN(value));
            const blocked = row.is_absent || row.is_malpractice;
            const percent = value !== null && !invalid && maxMarks
              ? Math.round((value / maxMarks) * 1000) / 10
              : null;

            return (
              <tr key={row.student_id} className={invalid ? 'is-invalid' : ''}>
                <td className="mono">{row.student_code}</td>
                <td>
                  <div className="dept-name">{row.student_name}</div>
                  {row.moved_section && (
                    <span className="type-chip type-cross-dept" title={`Now in ${row.student_section_name}`}>
                      TRANSFERRED
                    </span>
                  )}
                  {row.student_status && row.student_status !== 'ACTIVE' && (
                    <span className="status-badge inactive">{row.student_status}</span>
                  )}
                </td>
                <td>
                  <input
                    ref={(element) => { inputs.current[index] = element; }}
                    className={`mark-input ${invalid ? 'is-invalid' : ''}`}
                    type="number"
                    min="0"
                    max={maxMarks}
                    step="0.5"
                    inputMode="decimal"
                    value={raw}
                    placeholder="—"
                    disabled={disabled || blocked}
                    onKeyDown={(event) => handleKeyDown(event, index)}
                    onChange={(event) => onChange(row.student_id, { draft: event.target.value })}
                  />
                  {over && <span className="field-error">Max {maxMarks}</span>}
                  {under && <span className="field-error">Cannot be negative</span>}
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={row.is_absent}
                    disabled={disabled || row.is_malpractice}
                    onChange={(event) =>
                      onChange(row.student_id, {
                        is_absent: event.target.checked,
                        // An absence carries no mark; clearing it here keeps
                        // the screen honest before the API says so.
                        draft: event.target.checked ? '' : row.draft,
                      })
                    }
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={row.is_malpractice}
                    disabled={disabled || row.is_absent}
                    onChange={(event) =>
                      onChange(row.student_id, {
                        is_malpractice: event.target.checked,
                        draft: event.target.checked ? '' : row.draft,
                      })
                    }
                  />
                </td>
                <td>
                  {blocked ? (
                    <span className="status-badge inactive">
                      {row.is_absent ? ROW_STATE_LABEL.ABSENT : ROW_STATE_LABEL.MALPRACTICE}
                    </span>
                  ) : percent === null ? (
                    <span className="page-subtitle">{ROW_STATE_LABEL.PENDING}</span>
                  ) : (
                    <span className={`grade-chip tone-${gradeTone(null)}`}>
                      {percent}%
                      {passMarks !== null && value < passMarks && (
                        <em className="fail-flag"> below pass</em>
                      )}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
