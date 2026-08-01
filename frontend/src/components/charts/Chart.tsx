import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Glass } from "../ui";
import "./charts.css";

export interface ChartPoint {
  label: string;
  value: number | null;
}

/* Recharts needs concrete colour values, not CSS variables, so the palette
 * is read off the document once per render. Keeping it here means the charts
 * still follow the theme (including the dark-mode switch) without every
 * chart component duplicating the lookup. */
function themeColors() {
  if (typeof window === "undefined") {
    return { accent: "#e5261f", ink: "#0d0d0f", muted: "#5f6169", rule: "#e5e5e5" };
  }
  const styles = getComputedStyle(document.documentElement);
  return {
    accent: styles.getPropertyValue("--color-accent").trim() || "#e5261f",
    ink: styles.getPropertyValue("--color-ink").trim() || "#0d0d0f",
    muted: styles.getPropertyValue("--color-ink-muted").trim() || "#5f6169",
    rule: styles.getPropertyValue("--color-rule").trim() || "#e5e5e5",
  };
}

const AXIS_FONT_SIZE = 11;

function ChartFrame({
  title,
  caption,
  children,
  height = 260,
}: {
  title?: string;
  caption?: ReactNode;
  children: ReactNode;
  height?: number;
}) {
  return (
    <Glass className="chart-panel">
      {title && <h3 className="chart-panel__title">{title}</h3>}
      <div style={{ width: "100%", height }}>{children}</div>
      {caption && <p className="chart-panel__caption">{caption}</p>}
    </Glass>
  );
}

function EmptyChart({ title }: { title?: string }) {
  return (
    <Glass className="chart-panel">
      {title && <h3 className="chart-panel__title">{title}</h3>}
      <p className="chart-panel__empty">
        Not enough measured data to plot this yet.
      </p>
    </Glass>
  );
}

/** Shared tooltip so every chart reads identically. */
function chartTooltip(colors: ReturnType<typeof themeColors>) {
  return {
    contentStyle: {
      background: "var(--glass-bg-strong)",
      backdropFilter: "blur(16px)",
      border: `1px solid ${colors.rule}`,
      borderRadius: "var(--radius-sm)",
      boxShadow: "var(--shadow)",
      fontSize: 12,
      color: colors.ink,
    },
    labelStyle: { color: colors.muted, marginBottom: 4 },
    cursor: { stroke: colors.rule, strokeWidth: 1 },
  };
}

function hasData(points: ChartPoint[]): boolean {
  return points.filter((point) => point.value !== null).length >= 2;
}

export function TrendChart({
  points,
  title,
  caption,
  seriesName = "Value",
  height,
}: {
  points: ChartPoint[];
  title?: string;
  caption?: ReactNode;
  seriesName?: string;
  height?: number;
}) {
  if (!hasData(points)) return <EmptyChart title={title} />;

  const colors = themeColors();
  const tooltip = chartTooltip(colors);

  return (
    <ChartFrame title={title} caption={caption} height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors.accent} stopOpacity={0.22} />
              <stop offset="100%" stopColor={colors.accent} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={colors.rule} vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: AXIS_FONT_SIZE, fill: colors.muted }}
            tickLine={false}
            axisLine={{ stroke: colors.rule }}
            minTickGap={24}
          />
          <YAxis
            tick={{ fontSize: AXIS_FONT_SIZE, fill: colors.muted }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip {...tooltip} />
          <Area
            type="monotone"
            dataKey="value"
            name={seriesName}
            stroke={colors.accent}
            strokeWidth={2}
            fill="url(#trend-fill)"
            // A gap, not a zero — an unmeasured day had no reading at all.
            connectNulls={false}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function LineTrendChart({
  points,
  title,
  caption,
  seriesName = "Value",
  height,
}: {
  points: ChartPoint[];
  title?: string;
  caption?: ReactNode;
  seriesName?: string;
  height?: number;
}) {
  if (!hasData(points)) return <EmptyChart title={title} />;

  const colors = themeColors();
  const tooltip = chartTooltip(colors);

  return (
    <ChartFrame title={title} caption={caption} height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={colors.rule} vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: AXIS_FONT_SIZE, fill: colors.muted }}
            tickLine={false}
            axisLine={{ stroke: colors.rule }}
            minTickGap={24}
          />
          <YAxis
            tick={{ fontSize: AXIS_FONT_SIZE, fill: colors.muted }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip {...tooltip} />
          <Line
            type="monotone"
            dataKey="value"
            name={seriesName}
            stroke={colors.accent}
            strokeWidth={2}
            connectNulls={false}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function RankBarChart({
  points,
  title,
  caption,
  height,
}: {
  points: ChartPoint[];
  title?: string;
  caption?: ReactNode;
  height?: number;
}) {
  const measured = points.filter((point) => point.value !== null);
  if (measured.length === 0) return <EmptyChart title={title} />;

  const colors = themeColors();
  const tooltip = chartTooltip(colors);
  const best = Math.max(...measured.map((point) => point.value as number));

  return (
    <ChartFrame title={title} caption={caption} height={height ?? points.length * 40 + 32}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={points}
          layout="vertical"
          margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
        >
          <CartesianGrid stroke={colors.rule} horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: AXIS_FONT_SIZE, fill: colors.muted }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fontSize: AXIS_FONT_SIZE, fill: colors.muted }}
            tickLine={false}
            axisLine={false}
            width={140}
          />
          <Tooltip {...tooltip} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={18}>
            {points.map((point, index) => (
              <Cell
                key={index}
                // The leader is the accent; the rest recede, so the ranking
                // reads at a glance without a legend.
                fill={point.value === best ? colors.accent : colors.rule}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
