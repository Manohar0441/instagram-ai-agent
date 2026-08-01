import { formatNumber } from "../../lib/format";
import "./charts.css";

export interface BarDatum {
  label: string;
  value: number | null;
}

/**
 * A horizontal bar list — rows of label, track, value.
 *
 * Rows rather than vertical columns because the labels here are post
 * captions and metric names, which read far better set horizontally than
 * rotated 90 degrees under an axis.
 */
export function BarChart({
  data,
  format = formatNumber,
}: {
  data: BarDatum[];
  format?: (value: number | null) => string;
}) {
  const values = data
    .map((datum) => datum.value)
    .filter((value): value is number => value !== null);

  if (values.length === 0) {
    return (
      <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
        No measured values to compare yet.
      </p>
    );
  }

  const max = Math.max(...values) || 1;

  return (
    <div>
      {data.map((datum, index) => (
        <div className="bar-row" key={`${datum.label}-${index}`}>
          <span className="bar-row__label" title={datum.label}>
            {datum.label}
          </span>
          <span className="bar-row__track">
            <span
              className="bar-row__fill"
              style={{
                // A null value draws nothing at all, rather than a zero-width
                // bar that would read as a measured zero.
                width: datum.value === null ? "0" : `${(datum.value / max) * 100}%`,
              }}
            />
          </span>
          <span className="bar-row__value">{format(datum.value)}</span>
        </div>
      ))}
    </div>
  );
}
