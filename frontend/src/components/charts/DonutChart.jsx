import ChartEmpty from './ChartEmpty';
import ChartFrame from './ChartFrame';
import { formatCount, formatPercent, pct, seriesColor } from './chartUtils';

const SIZE = 200;
const THICKNESS = 22;
const R = (SIZE - THICKNESS) / 2;
const C = 2 * Math.PI * R;

/**
 * Composition, as stroked arcs on one circle.
 *
 * Slices are drawn with stroke-dasharray rather than wedge paths: one element
 * per slice, no path arithmetic, and the join between slices stays exact at
 * any size.
 */
export default function DonutChart({
  data = [],
  centerValue,
  centerLabel,
  maxSlices = 6,
  emptyTitle = 'Nothing to show yet',
  emptyHint,
}) {
  const positive = data.filter((item) => item.value > 0);
  const total = positive.reduce((sum, item) => sum + item.value, 0);

  if (!total) {
    return <ChartEmpty title={emptyTitle} hint={emptyHint} />;
  }

  // Everything past the slice limit folds into a single honest "Other".
  const head = positive.slice(0, maxSlices);
  const tail = positive.slice(maxSlices);
  const slices = [...head];
  if (tail.length) {
    slices.push({
      id: '__other',
      label: `Other (${tail.length})`,
      value: tail.reduce((sum, item) => sum + item.value, 0),
      isOther: true,
    });
  }

  let offset = 0;
  const arcs = slices.map((slice, index) => {
    const share = pct(slice.value, total);
    const length = (share / 100) * C;
    const arc = {
      ...slice,
      share,
      color: slice.isOther ? 'var(--chart-other)' : seriesColor(index),
      dash: `${length} ${C - length}`,
      // -90deg puts the first slice at 12 o'clock; the offset walks clockwise.
      rotation: (offset / 100) * 360 - 90,
    };
    offset += share;
    return arc;
  });

  return (
    <ChartFrame
      title={centerLabel ? `${centerLabel} by share` : 'Composition'}
      description={slices
        .map((s) => `${s.label}: ${s.value} (${formatPercent(pct(s.value, total))})`)
        .join('. ')}
      columns={['Category', 'Count', 'Share']}
      rows={slices.map((s) => [s.label, formatCount(s.value), formatPercent(pct(s.value, total))])}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="chart-donut"
      footer={
        <ul className="chart-legend-list">
          {arcs.map((arc) => (
            <li key={arc.id}>
              <span className="dot" style={{ background: arc.color }} aria-hidden="true" />
              <span className="chart-legend-label">{arc.label}</span>
              <strong>{formatCount(arc.value)}</strong>
              <span className="chart-legend-share">{formatPercent(arc.share, 0)}</span>
            </li>
          ))}
        </ul>
      }
    >
      <circle
        cx={SIZE / 2}
        cy={SIZE / 2}
        r={R}
        fill="none"
        stroke="var(--chart-track)"
        strokeWidth={THICKNESS}
      />
      {arcs.map((arc) => (
        <circle
          key={arc.id}
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={R}
          fill="none"
          stroke={arc.color}
          strokeWidth={THICKNESS}
          strokeDasharray={arc.dash}
          transform={`rotate(${arc.rotation} ${SIZE / 2} ${SIZE / 2})`}
        />
      ))}

      {centerValue != null && (
        <text
          x={SIZE / 2}
          y={SIZE / 2 - 2}
          textAnchor="middle"
          className="chart-center-value"
        >
          {formatCount(centerValue)}
        </text>
      )}
      {centerLabel && (
        <text x={SIZE / 2} y={SIZE / 2 + 18} textAnchor="middle" className="chart-center-label">
          {centerLabel}
        </text>
      )}
    </ChartFrame>
  );
}
