import ChartFrame from './ChartFrame';
import { clamp, formatPercent } from './chartUtils';

const SIZE = 180;
const THICKNESS = 18;
const R = (SIZE - THICKNESS) / 2;
const C = 2 * Math.PI * R;

/** One percentage, large. Tinted against a threshold rather than always green. */
export default function GaugeRing({
  value = 0,
  label,
  caption,
  threshold = 75,
  description,
}) {
  const safe = clamp(Number(value) || 0, 0, 100);
  const length = (safe / 100) * C;
  const color = safe < threshold ? 'var(--accent-red)' : 'var(--accent-green-bright)';

  return (
    <ChartFrame
      title={label || 'Attendance'}
      description={description || `${formatPercent(safe)} against a ${threshold}% minimum.`}
      columns={['Measure', 'Value']}
      rows={[[label || 'Attendance', formatPercent(safe)], ['Minimum', `${threshold}%`]]}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="chart-gauge"
      footer={caption ? <p className="chart-caption">{caption}</p> : null}
    >
      <circle
        cx={SIZE / 2}
        cy={SIZE / 2}
        r={R}
        fill="none"
        stroke="var(--chart-track)"
        strokeWidth={THICKNESS}
      />
      <circle
        cx={SIZE / 2}
        cy={SIZE / 2}
        r={R}
        fill="none"
        stroke={color}
        strokeWidth={THICKNESS}
        strokeLinecap="round"
        strokeDasharray={`${length} ${C - length}`}
        transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
      />
      <text x={SIZE / 2} y={SIZE / 2 + 4} textAnchor="middle" className="chart-gauge-value">
        {formatPercent(safe, safe % 1 === 0 ? 0 : 1)}
      </text>
      {label && (
        <text x={SIZE / 2} y={SIZE / 2 + 26} textAnchor="middle" className="chart-center-label">
          {label}
        </text>
      )}
    </ChartFrame>
  );
}
