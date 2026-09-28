/**
 * What a chart shows when there is nothing to draw.
 *
 * Deliberately not a zeroed chart: an empty axis reads as "the value is zero",
 * which is a different and usually false statement.
 */
export default function ChartEmpty({ title, hint, action }) {
  return (
    <div className="chart-empty">
      <p className="chart-empty-title">{title}</p>
      {hint && <p className="chart-empty-hint">{hint}</p>}
      {action}
    </div>
  );
}
