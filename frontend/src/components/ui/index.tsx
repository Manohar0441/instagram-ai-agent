import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { useId } from "react";

import "./ui.css";

// ------------------------------------------------------------- Button

type ButtonVariant = "default" | "primary" | "quiet" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  small?: boolean;
  loading?: boolean;
}

export function Button({
  variant = "default",
  small = false,
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
        aria-describedby={[hint ? hintId : "", error ? errorId : ""].filter(Boolean).join(" ") || undefined}
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
      {title && <div className="callout__title">{title}</div>}
      <div>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------- StatBlock

export function StatBlock({
  label,
  value,
  delta,
  deltaDirection,
}: {
  label: string;
  value: string;
  delta?: string;
  deltaDirection?: "up" | "down" | "flat";
}) {
  // The arrow carries the direction so the meaning survives without colour.
  const glyph =
    deltaDirection === "up" ? "↑" : deltaDirection === "down" ? "↓" : "→";

  return (
    <div className="stat-block">
      <span className="stat-block__label">{label}</span>
      <span className="stat-block__value">{value}</span>
      {delta && (
        <span
          className={`stat-block__delta ${
            deltaDirection === "up"
              ? "stat-block__delta--up"
              : deltaDirection === "down"
                ? "stat-block__delta--down"
                : ""
          }`}
        >
          {glyph} {delta}
        </span>
      )}
    </div>
  );
}

// --------------------------------------------------------- EmptyState

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-state__title">{title}</div>
      <div className="empty-state__body">{body}</div>
      {action}
    </div>
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
