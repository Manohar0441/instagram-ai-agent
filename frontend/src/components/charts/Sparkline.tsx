/**
 * A tiny inline trend line for stat cards.
 *
 * Hand-rolled rather than a charting library: at 80×28px there are no axes,
 * ticks, tooltips or legend to configure, so a library would add weight and
 * a second theming surface for the sake of one `<path>`.
 *
 * Nulls break the line into segments rather than being drawn as zero — an
 * unmeasured day is not a day with no activity.
 */
export function Sparkline({ values }: { values: (number | null)[] }) {
  const measured = values.filter((value): value is number => value !== null);
  if (measured.length < 2) return null;

  const width = 80;
  const height = 28;
  const padding = 2;

  const max = Math.max(...measured);
  const min = Math.min(...measured);
  // A flat series would divide by zero; give it a nominal range so the line
  // sits centred rather than collapsing onto the baseline.
  const range = max - min || Math.abs(max) || 1;

  const x = (index: number) =>
    padding + (index / (values.length - 1 || 1)) * (width - padding * 2);
  const y = (value: number) =>
    height - padding - ((value - min) / range) * (height - padding * 2);

  const segments: string[] = [];
  let current: string[] = [];

  values.forEach((value, index) => {
    if (value === null) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
      return;
    }
    current.push(`${current.length === 0 ? "M" : "L"} ${x(index)} ${y(value)}`);
  });
  if (current.length > 1) segments.push(current.join(" "));

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height="100%"
      aria-hidden="true"
      focusable="false"
    >
      {segments.map((segment) => (
        <path
          key={segment}
          d={segment}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </svg>
  );
}
