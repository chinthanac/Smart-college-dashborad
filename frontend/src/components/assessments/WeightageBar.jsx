import { MAX_TOTAL_WEIGHTAGE } from '../../services/assessmentService';

/**
 * A class's 100%, drawn as the components that have claimed it.
 *
 * This exists so the constraint is visible while the number is being typed,
 * rather than explained by a rejection afterwards. The API enforces the same
 * rule and names the same consumers — this is the version you can see.
 */
export default function WeightageBar({ budget, pending = 0, excludeId = null }) {
  if (!budget) return null;

  const consumers = budget.consumers.filter((item) => item.assessment_id !== excludeId);
  const allocated = consumers.reduce((sum, item) => sum + item.weightage_percent, 0);
  const requested = Number(pending) || 0;
  const remaining = MAX_TOTAL_WEIGHTAGE - allocated - requested;
  const overflow = remaining < -0.01;

  return (
    <div className="weightage-bar">
      <div className="weightage-head">
        <span className="weightage-title">Weightage used</span>
        <span className={`weightage-remaining ${overflow ? 'is-over' : ''}`}>
          {overflow
            ? `${Math.abs(remaining).toFixed(1)}% over`
            : `${remaining.toFixed(1)}% left`}
        </span>
      </div>

      <div className="weightage-track">
        {consumers.map((item, index) => (
          <div
            key={item.assessment_id}
            className={`weightage-seg seg-${(index % 5) + 1}`}
            style={{ width: `${Math.min(item.weightage_percent, 100)}%` }}
            title={`${item.name} — ${item.weightage_percent}%`}
          />
        ))}
        {requested > 0 && (
          <div
            className={`weightage-seg ${overflow ? 'is-over' : 'is-pending'}`}
            style={{ width: `${Math.min(requested, 100)}%` }}
            title={`This assessment — ${requested}%`}
          />
        )}
      </div>

      {consumers.length > 0 ? (
        <ul className="weightage-legend">
          {consumers.map((item, index) => (
            <li key={item.assessment_id}>
              <span className={`weightage-dot seg-${(index % 5) + 1}`} />
              {item.name} · {item.weightage_percent}%
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-note">Nothing allocated yet — the whole 100% is free.</p>
      )}
    </div>
  );
}
