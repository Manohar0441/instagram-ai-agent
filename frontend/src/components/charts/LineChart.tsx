import { useId } from "react";

import { formatNumber } from "../../lib/format";
import "./charts.css";

export interface LinePoint {
  label: string;
  value: number | null;
}

/**
 * A single-series line chart, hand-rolled in SVG.
 *
 * No chart library: every one of them ships gridlines, shadowed tooltips and
 * legend dots that would have to be turned off one at a time. One baseline
 * rule, one accent stroke, ticks at the ends, and the value labelled at the
 * end of the line rather than in a legend.
 *
 * Null values are gaps, not zeroes — the series is split into segments so an
 * unmeasured day never draws a line down to the axis.
 */
export function LineChart({
  points,
  height = 240,
  label,
  valueLabel,
}: {
  points: LinePoint[];
  height?: number;
  label: string;
  valueLabel?: string;
}) {
  const titleId = useId();
  const measured = points.filter((point) => point.value !== null);

  if (measured.length < 2) {
    return (
      <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
        Not enough measured data points to plot a trend yet.
      </p>
    );
  }

  const width = 1000;
  const padding = { top: 16, right: 56, bottom: 28, left: 8 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const values = measured.map((point) => point.value as number);
  const max = Math.max(...values);
  const min = Math.min(...values);
  // A flat series would divide by zero; give it a nominal range so the line
  // sits centred rather than collapsing onto the baseline.
  const range = max - min || Math.abs(max) || 1;

  const x = (index: number) =>
    padding.left + (index / (points.length - 1 || 1)) * plotWidth;
  const y = (value: number) =>
    padding.top + plotHeight - ((value - min) / range) * plotHeight;

  // Break the path wherever the data is missing.
  const segments: string[] = [];
  let current: string[] = [];

  points.forEach((point, index) => {
    if (point.value === null) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
      return;
    }
    current.push(`${current.length === 0 ? "M" : "L"} ${x(index)} ${y(point.value)}`);
  });
  if (current.length > 1) segments.push(current.join(" "));

  const lastIndex = points.reduce(
    (last, point, index) => (point.value !== null ? index : last),
    0,
  );
  const lastValue = points[lastIndex]?.value ?? null;

  return (
    <figure className="chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={titleId}
        preserveAspectRatio="none"
        className="chart__svg"
      >
        <title id={titleId}>{label}</title>

        {/* The single baseline — the only rule in the plot area. */}
        <line
          x1={padding.left}
          y1={padding.top + plotHeight}
          x2={padding.left + plotWidth}
          y2={padding.top + plotHeight}
          className="chart__baseline"
        />

        {segments.map((segment) => (
          <path key={segment} d={segment} className="chart__line" />
        ))}

        {lastValue !== null && (
          <>
            <circle cx={x(lastIndex)} cy={y(lastValue)} r={3} className="chart__marker" />
            {/* Labelled in place, so there is no legend to cross-reference. */}
            <text
              x={x(lastIndex) + 8}
              y={y(lastValue) + 4}
              className="chart__value-label"
            >
              {formatNumber(lastValue)}
            </text>
          </>
        )}
      </svg>

      <figcaption className="chart__caption">
        <span>{points[0]?.label}</span>
        {valueLabel && <span className="chart__series-label">{valueLabel}</span>}
        <span>{points[points.length - 1]?.label}</span>
      </figcaption>
    </figure>
  );
}
