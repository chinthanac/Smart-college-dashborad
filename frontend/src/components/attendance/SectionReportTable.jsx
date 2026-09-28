import { STANDING_CLASS, STANDING_LABEL } from '../../services/attendanceService';

/** Per-student standing across a section. */
export default function SectionReportTable({ report, loading }) {
  if (loading) return <p className="empty-note">Building the report...</p>;

  if (!report) {
    return <p className="empty-note">Choose a section to see how its students are doing.</p>;
  }

  if (!report.students.length) {
    return (
      <p className="empty-note">
        Nothing has been marked for {report.section_name} in this period yet.
      </p>
    );
  }

  return (
    <div className="department-table-wrap scroll-table">
      <table className="department-table">
        <thead>
          <tr>
            <th>Roll No</th>
            <th>Student</th>
            <th>Attended</th>
            <th>Percentage</th>
          </tr>
        </thead>
        <tbody>
          {report.students.map((row) => (
            <tr key={row.student_id}>
              <td className="mono">{row.student_code}</td>
              <td>
                <div className="dept-name">{row.student_name}</div>
                {row.student_status && row.student_status !== 'ACTIVE' && (
                  <span className="status-badge inactive">{row.student_status}</span>
                )}
              </td>
              <td>
                {row.present_count}/{row.countable_sessions}
                {row.excused_count > 0 && (
                  <div className="dept-desc">{row.excused_count} excused</div>
                )}
              </td>
              <td className="attendance-percent-cell">
                <div className="coverage-bar">
                  <div
                    className="coverage-bar-fill"
                    style={{
                      width: `${Math.min(100, row.attendance_percentage)}%`,
                      background:
                        row.attendance_percentage < report.threshold ? '#dc2626' : '#22c55e',
                    }}
                  />
                </div>
                <strong>{row.attendance_percentage}%</strong>{' '}
                <span className={`coverage-status ${STANDING_CLASS[row.status]}`}>
                  {STANDING_LABEL[row.status]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
