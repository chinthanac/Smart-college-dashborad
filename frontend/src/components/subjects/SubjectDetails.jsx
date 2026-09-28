import SubjectActivityPanel from './SubjectActivityPanel';

export default function SubjectDetails({ subject, onClose, onEdit }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3>Subject Details</h3>

        <div className="profile-hero">
          <strong>{subject.name}</strong>
          <span className="mono">{subject.subject_code}</span>
          <span className={`status-badge ${subject.is_active ? 'active' : 'inactive'}`}>
            {subject.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>

        <div className="profile-section-title">Academic Placement</div>
        <div className="profile-grid">
          <div><span>Department</span><strong>{subject.department_name} ({subject.department_code})</strong></div>
          <div><span>Course</span><strong>{subject.course_name}</strong></div>
          <div><span>Semester</span><strong>{subject.semester_name}</strong></div>
          <div><span>Academic Year</span><strong>{subject.academic_year_name || '—'}</strong></div>
        </div>

        <div className="profile-section-title">Curriculum</div>
        <div className="profile-grid">
          <div><span>Type</span><strong>{subject.subject_type}</strong></div>
          <div><span>Credits</span><strong>{subject.credits}</strong></div>
          <div><span>Lecture Hours</span><strong>{subject.lecture_hours}</strong></div>
          <div><span>Tutorial Hours</span><strong>{subject.tutorial_hours}</strong></div>
          <div><span>Practical Hours</span><strong>{subject.practical_hours}</strong></div>
          <div><span>Total per Week</span><strong>{subject.total_hours} hrs</strong></div>
          <div className="span-2"><span>Description</span><strong>{subject.description || '—'}</strong></div>
        </div>

        <SubjectActivityPanel subjectId={subject.id} />

        <div className="modal-actions">
          <button type="button" className="secondary-btn" onClick={onClose}>Close</button>
          <button type="button" className="primary-btn" onClick={() => onEdit(subject)}>Edit Subject</button>
        </div>
      </div>
    </div>
  );
}
