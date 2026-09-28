import ChartEmpty from './ChartEmpty';
import ChartFrame from './ChartFrame';
import { formatPercent } from './chartUtils';

const W = 560;
const H = 220;
const PAD = { top: 16, right: 16, bottom: 34, left: 38 };

/**
 * One series over time, as a line with a soft area beneath it.
 *
 * Points carrying no data are drawn as a gap, not as zero — a month with no
 * classes taught is not a month of 0% attendance, and joining across it would
 * assert something the data does not say.
 */
export default function SeriesChart({
  points = [],
  valueKey = 'attendance_percentage',
  labelKey = 'label',
  title = 'Attendance by month',
  emptyTitle = 'No attendance has been marked yet',
  emptyHint,
  threshold = 75,
}) {
  const withData = points.filter((point) => point.has_data);
  if (!points.length || !withData.length) {
    return <ChartEmpty title={emptyTitle} hint={emptyHint} />;
  }

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  // A percentage axis is always 0-100: rescaling to the data would make a
  // good month and a bad month look identical.
  const x = (index) =>
    PAD.left + (points.length === 1 ? plotW / 2 : (index / (points.length - 1)) * plotW);
  const y = (value) => PAD.top + plotH - (Math.max(0, Math.min(100, value)) / 100) * plotH;

  const plotted = points
    .map((point, index) => ({ point, index }))
    .filter(({ point }) => point.has_data)
    .map(({ point, index }) => ({
      x: x(index),
      y: y(point[valueKey]),
      point,
      index,
    }));

  const line = plotted.map((p) => `${p.x},${p.y}`).join(' ');
  const area = plotted.length > 1
    ? `${plotted[0].x},${PAD.top + plotH} ${line} ${plotted[plotted.length - 1].x},${PAD.top + plotH}`
    : null;

  const gridValues = [0, 25, 50, 75, 100];

  return (
    <ChartFrame
      title={title}
      description={withData
        .map((p) => `${p[labelKey]}: ${formatPercent(p[valueKey])}`)
        .join('. ')}
      columns={['Month', 'Classes held', 'Attendance']}
      rows={points.map((p) => [
        p[labelKey],
        p.held_sessions ?? 0,
        p.has_data ? formatPercent(p[valueKey]) : 'No classes',
      ])}
      viewBox={`0 0 ${W} ${H}`}
      className="chart-series"
    >
      {gridValues.map((value) => (
        <g key={value}>
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={y(value)}
            y2={y(value)}
            stroke={value === threshold ? 'var(--accent-red)' : 'var(--chart-grid)'}
            strokeWidth="1"
            strokeDasharray={value === threshold ? '4 4' : undefined}
            opacity={value === threshold ? 0.5 : 1}
          />
          <text x={PAD.left - 8} y={y(value) + 4} textAnchor="end" className="chart-axis-label">
            {value}
          </text>
        </g>
      ))}

      {area && <polygon points={area} fill="var(--chart-series-1)" opacity="0.12" />}

      {plotted.length > 1 && (
        <polyline
          points={line}
          fill="none"
          stroke="var(--chart-series-1)"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      )}

      {plotted.map((p) => (
        <circle
          key={p.index}
          cx={p.x}
          cy={p.y}
          r={plotted.length > 8 ? 3 : 4}
          fill="var(--surface-1)"
          stroke="var(--chart-series-1)"
          strokeWidth="2"
        />
      ))}

      {points.map((point, index) => {
        // With twelve months every label collides, so show every other one —
        // counted back from the END, because the last point is the anchor the
        // panel header names ("12 months to Sep 2026") and it must be labelled.
        const show = points.length <= 7 || (points.length - 1 - index) % 2 === 0;
        if (!show) return null;
        return (
          <text
            key={point.month ?? index}
            x={x(index)}
            y={H - 10}
            textAnchor="middle"
            className={`chart-axis-label ${point.has_data ? '' : 'is-empty'}`}
          >
            {String(point[labelKey]).split(' ')[0]}
          </text>
        );
      })}
    </ChartFrame>
  );
}
