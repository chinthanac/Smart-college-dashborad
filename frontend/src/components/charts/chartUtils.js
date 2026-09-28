/** The one division guard. Every percentage in every chart goes through it. */
export const pct = (value, total) => (total > 0 ? (value / total) * 100 : 0);

export const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value));

export const formatPercent = (value, digits = 1) =>
  value == null ? '—' : `${Number(value).toFixed(digits)}%`;

export const formatCount = (value) => Number(value ?? 0).toLocaleString();

/**
 * Series colours come from tokens, never from literals — that is what keeps
 * the legend, the donut and the bars showing the same series in the same
 * colour, which this stylesheet historically did not.
 */
export const SERIES_TOKENS = [1, 2, 3, 4, 5, 6].map((i) => `var(--chart-series-${i})`);

/**
 * Past the sixth series we FOLD into "Other" rather than generating a hue.
 * An invented colour implies a category we chose to distinguish; "Other" is
 * the honest label for one we did not.
 */
export const seriesColor = (index) => SERIES_TOKENS[index] ?? 'var(--chart-other)';

/** SVG angles run clockwise from 12 o'clock; maths runs anticlockwise from 3. */
export const polarToXY = (cx, cy, r, degrees) => {
  const radians = ((degrees - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(radians), cy + r * Math.sin(radians)];
};

/** A round number at or above `value`, so an axis never ends on 3,847. */
export const niceMax = (value) => {
  if (!value || value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
};
