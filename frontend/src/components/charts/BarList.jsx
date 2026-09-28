import ChartEmpty from './ChartEmpty';
import { clamp, formatPercent, pct } from './chartUtils';

/**
 * A ranked list of meters.
 *
 * Deliberately HTML rather than SVG: these rows carry a label, two numbers
 * and a bar, which a table does better than a drawing, and it inherits the
 * .coverage-bar styling the rest of the app already uses for exactly this.
 */
export default function BarList({
  rows = [],
  emptyTitle = 'Nothing to show yet',
  emptyHint,
}) {
  if (!rows.length) {
    return <ChartEmpty title={emptyTitle} hint={emptyHint} />;
  }

  return (
    <ul className="bar-list">
      {rows.map((row) => {
        const share = row.percentage ?? pct(row.value, row.max);
        return (
          <li key={row.id} className="bar-list-row">
            <div className="bar-list-head">
              <span className="bar-list-label">{row.label}</span>
              <span className="bar-list-value">{row.caption}</span>
            </div>
            <div className="coverage-bar">
              <div
                className="coverage-bar-fill"
                style={{
                  width: `${clamp(share, 0, 100)}%`,
                  background:
                    row.tone === 'danger'
                      ? 'var(--accent-red)'
                      : row.tone === 'warn'
                        ? 'var(--accent-amber)'
                        : 'var(--chart-series-1)',
                }}
              />
            </div>
            {row.hint && <span className="bar-list-hint">{row.hint}</span>}
            <span className="visually-hidden">{formatPercent(share)}</span>
          </li>
        );
      })}
    </ul>
  );
}
