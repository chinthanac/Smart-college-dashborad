import { useId } from 'react';

/**
 * Every chart's outer shell.
 *
 * Two things are centralised here because getting either wrong is invisible
 * until it is badly wrong:
 *
 *  1. Sizing. The <svg> carries a viewBox and width="100%" and NO height
 *     attribute. An SVG with only a viewBox has no intrinsic size inside a
 *     flex or grid item and collapses to zero height — the single most
 *     common way a hand-rolled chart silently disappears.
 *  2. Access. A chart is an image to a screen reader, so it gets role="img"
 *     with a title and description, plus the same numbers as a real table
 *     underneath it. Anyone who cannot see the drawing can still read the data.
 */
export default function ChartFrame({
  title,
  description,
  columns = [],
  rows = [],
  viewBox,
  className = '',
  children,
  footer,
}) {
  const id = useId();

  return (
    <figure className={`chart-figure ${className}`}>
      <svg
        className="chart"
        viewBox={viewBox}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-labelledby={`${id}-title ${id}-desc`}
        focusable="false"
      >
        <title id={`${id}-title`}>{title}</title>
        <desc id={`${id}-desc`}>{description}</desc>
        {children}
      </svg>

      {footer}

      {rows.length > 0 && (
        <table className="visually-hidden">
          <caption>{title}</caption>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} scope="col">{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row[0] ?? index}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </figure>
  );
}
