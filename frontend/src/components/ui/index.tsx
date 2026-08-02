import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { useId } from "react";

import { Sparkline } from "../charts/Sparkline";

// -------------------------------------------------------------- Panel

/** The base card surface every panel and card is built on: a solid fill,
 * a firm border, and a hard offset shadow — swiss.css's own idiom. */
export function Panel({
  as: Tag = "div",
  interactive = false,
  className = "",
  children,
  ...rest
}: {
  as?: "div" | "section" | "article" | "aside";
  interactive?: boolean;
  className?: string;
  children: ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) {
  const classes = [
    "swiss-panel",
    interactive ? "swiss-panel--interactive" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Tag className={classes} {...rest}>
      {children}
    </Tag>
  );
}

// ------------------------------------------------------------- Button

type ButtonVariant = "default" | "primary" | "quiet" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  small?: boolean;
  icon?: boolean;
  loading?: boolean;
}

export function Button({
  variant = "default",
  small = false,
  icon = false,
  loading = false,
  disabled,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  const classes = [
    "button",
    variant !== "default" ? `button--${variant}` : "",
    small ? "button--small" : "",
    icon ? "button--icon" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button className={classes} disabled={disabled || loading} {...rest}>
      {loading && <span className="spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

// -------------------------------------------------------------- Field

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: ReactNode;
  error?: string | null;
}

export function Field({ label, hint, error, ...rest }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;

  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {hint && (
        <span className="field__hint" id={hintId}>
          {hint}
        </span>
      )}
      <input
        className="field__input"
        id={id}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={
          [hint ? hintId : "", error ? errorId : ""].filter(Boolean).join(" ") || undefined
        }
        {...rest}
      />
      {error && (
        <span className="field__error" id={errorId} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

// ------------------------------------------------------------ Callout

export function Callout({
  title,
  tone = "neutral",
  children,
}: {
  title?: string;
  tone?: "neutral" | "error";
  children: ReactNode;
}) {
  return (
    <div
      className={`callout ${tone === "error" ? "callout--error" : ""}`}
      role={tone === "error" ? "alert" : undefined}
    >
      <div>
        {title && <div className="callout__title">{title}</div>}
        <div>{children}</div>
      </div>
    </div>
  );
}

// -------------------------------------------------------------- Badge

export function Badge({
  children,
  variant = "default",
}: {
  children: ReactNode;
  variant?: "default" | "accent" | "solid";
}) {
  return (
    <span className={`badge ${variant !== "default" ? `badge--${variant}` : ""}`}>
      {children}
    </span>
  );
}

// ------------------------------------------------------------ Tooltip

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="has-tooltip" tabIndex={0}>
      {children}
      <span className="has-tooltip__bubble" role="tooltip">
        {label}
      </span>
    </span>
  );
}

// ----------------------------------------------------------- StatCard

export type TrendDirection = "up" | "down" | "flat";

export function StatCard({
  label,
  value,
  icon,
  delta,
  direction,
  note,
  tooltip,
  sparkline,
}: {
  label: string;
  value: string;
  icon?: ReactNode;
  delta?: string;
  direction?: TrendDirection;
  note?: string;
  tooltip?: string;
  sparkline?: (number | null)[];
}) {
  // The arrow carries the direction, so meaning survives without colour.
  const glyph = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";

  const labelNode = tooltip ? (
    <Tooltip label={tooltip}>
      <span className="stat-card__label">{label}</span>
    </Tooltip>
  ) : (
    <span className="stat-card__label">{label}</span>
  );

  return (
    <Panel className="stat-card" interactive>
      <div className="stat-card__head">
        {labelNode}
        {icon && (
          <span className="stat-card__icon" aria-hidden="true">
            {icon}
          </span>
        )}
      </div>

      <span className="stat-card__value">{value}</span>

      <div className="stat-card__foot">
        {delta ? (
          <span className={`stat-card__delta stat-card__delta--${direction ?? "flat"}`}>
            <span aria-hidden="true">{glyph}</span>
            {delta}
          </span>
        ) : (
          note && <span className="stat-card__note">{note}</span>
        )}

        {sparkline && sparkline.length > 1 && (
          <span className="stat-card__sparkline">
            <Sparkline values={sparkline} />
          </span>
        )}
      </div>
    </Panel>
  );
}

// --------------------------------------------------------- EmptyState

export function EmptyState({
  art = "◍",
  title,
  body,
  actions,
}: {
  art?: ReactNode;
  title: string;
  body: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <Panel className="empty-state">
      <span className="empty-state__art" aria-hidden="true">
        {art}
      </span>
      <div>
        <div className="empty-state__title">{title}</div>
        <div className="empty-state__body">{body}</div>
      </div>
      {actions && <div className="empty-state__actions">{actions}</div>}
    </Panel>
  );
}

// ------------------------------------------------------------ Loading

export function LoadingPage({ label = "Loading" }: { label?: string }) {
  return (
    <div className="loading-page">
      <span className="spinner spinner--page" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

/** Placeholder cards that hold the layout the real content will occupy. */
export function SkeletonCards({ count = 4 }: { count?: number }) {
  return (
    <div className="grid">
      {Array.from({ length: count }).map((_, index) => (
        <div className="col-3" key={index}>
          <Panel className="skeleton-card">
            <div className="skeleton skeleton-line skeleton-line--sm" />
            <div className="skeleton skeleton-line skeleton-line--xl" />
            <div className="skeleton skeleton-line skeleton-line--md" />
          </Panel>
        </div>
      ))}
    </div>
  );
}

export function SkeletonBlock({ lines = 3 }: { lines?: number }) {
  const widths = ["--lg", "--md", "--sm"];
  return (
    <Panel className="skeleton-card">
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className={`skeleton skeleton-line skeleton-line${widths[index % widths.length]}`}
        />
      ))}
    </Panel>
  );
}

// -------------------------------------------------- SegmentedControl

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className="segmented__option"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
