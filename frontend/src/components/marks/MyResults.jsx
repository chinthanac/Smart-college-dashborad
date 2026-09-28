import useAsyncPanel from '../../hooks/useAsyncPanel';
import assessmentService, { gradeTone, showNumber } from '../../services/assessmentService';

/**
 * A student's own result.
 *
 * Every "we do not know" is rendered as such. An incomplete subject shows its
 * reason, not a zero; a withheld SGPA says why it is withheld. The rule this
 * screen exists to respect is that a number shown here will be believed.
 */
export default function MyResults() {
  const { data, loading, error } = useAsyncPanel(() => assessmentService.myResult(), []);

  if (loading) return <p className="empty-note">Loading your results…</p>;
  if (error) return <div className="error-box" role="alert">{error}</div>;
  if (!data) return null;

  return (
    <section className="panel-card" id="my-results">
      <header className="panel-head">
        <div>
          <h3>My Results</h3>
          <span className="page-subtitle">
            {data.semester_name || 'Current semester'} · {data.section_name}
          </span>
        </div>
        <div className="panel-head-meta">
          {data.has_data ? (
            <>
              <span className="sgpa-badge">SGPA {data.sgpa}</span>
              <span className="page-subtitle">{data.overall_percent}% overall</span>
            </>
          ) : (
            <span className="status-badge inactive">SGPA pending</span>
          )}
        </div>
      </header>

      {!data.has_data && data.reason && (
        <div className="notice-box" role="status">{data.reason}</div>
      )}

      {data.attendance_percent !== null && data.attendance_short && (
        <div className="notice-box warn" role="status">
          Attendance is {data.attendance_percent}%, below the {data.attendance_threshold}% mark.
          This is recorded alongside your result, not applied to it.
        </div>
      )}

      {!data.subjects.length ? (
        <p className="empty-note">No results have been published yet.</p>
      ) : (
        <div className="department-table-wrap scroll-table">
          <table className="department-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Credits</th>
                <th>Score</th>
                <th>Grade</th>
                <th>Components</th>
              </tr>
            </thead>
            <tbody>
              {data.subjects.map((subject) => (
                <tr key={subject.subject_id}>
                  <td>
                    <div className="mono">{subject.subject_code}</div>
                    <div className="page-subtitle">{subject.subject_name}</div>
                  </td>
                  <td className="mono">{subject.credits}</td>
                  <td className="mono">{showNumber(subject.percent, '%')}</td>
                  <td>
                    {subject.grade_letter ? (
                      <span className={`grade-chip tone-${gradeTone(subject.grade_letter)}`}>
                        {subject.grade_letter}
                      </span>
                    ) : (
                      <span className="page-subtitle">Pending</span>
                    )}
                  </td>
                  <td>
                    {subject.has_data ? (
                      <ul className="breakdown-list">
                        {subject.breakdown.map((item) => (
                          <li key={item.assessment_id}>
                            {item.name}: {item.is_absent
                              ? 'Absent'
                              : item.is_malpractice
                                ? 'Malpractice'
                                : `${showNumber(item.marks_obtained)} / ${item.max_marks}`}
                            <span className="page-subtitle"> ({item.weightage_percent}%)</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="page-subtitle">{subject.reason}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
