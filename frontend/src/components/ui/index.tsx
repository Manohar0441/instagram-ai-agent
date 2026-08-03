import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { useCallback, useId, useLayoutEffect, useRef } from "react";

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

// ----------------------------------------------------------- Textarea

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: ReactNode;
  error?: string | null;
}

export function Textarea({ label, hint, error, ...rest }: TextareaProps) {
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
      <textarea
        className="field__textarea"
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

// -------------------------------------------------------------- Select

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  options: { value: string; label: string }[];
}

export function Select({ label, hint, error, options, ...rest }: SelectProps) {
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
      <select
        className="field__select"
        id={id}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={
          [hint ? hintId : "", error ? errorId : ""].filter(Boolean).join(" ") || undefined
        }
        {...rest}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
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

/** Viewport margin the bubble should never cross, in pixels. */
const TOOLTIP_VIEWPORT_PADDING = 12;

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const triggerRef = useRef<HTMLSpanElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);

  // The bubble is CSS-anchored to the trigger's left edge (necessary for it
  // to track the trigger at all), which overflows the viewport whenever the
  // trigger sits anywhere but the far left - a stat card in a later grid
  // column, for instance. Measuring on show and nudging back on-screen is
  // the only way to keep both properties (tracks the trigger, never clips)
  // at once; a fixed CSS position can only ever have one of them.
  const clampPosition = useCallback(() => {
    const trigger = triggerRef.current;
    const bubble = bubbleRef.current;
    if (!trigger || !bubble) return;

    bubble.style.left = "0px";
    const triggerRect = trigger.getBoundingClientRect();
    const bubbleWidth = bubble.offsetWidth;
    const viewportWidth = document.documentElement.clientWidth;

    const naturalRight = triggerRect.left + bubbleWidth;
    const overflowRight = naturalRight - (viewportWidth - TOOLTIP_VIEWPORT_PADDING);
    const overflowLeft = TOOLTIP_VIEWPORT_PADDING - triggerRect.left;

    if (overflowRight > 0) {
      bubble.style.left = `${-overflowRight}px`;
    } else if (overflowLeft > 0) {
      bubble.style.left = `${overflowLeft}px`;
    }
  }, []);

  // The bubble stays mounted (just opacity:0) even when closed, so an
  // unclamped default position still widens the page's scrollable area -
  // clamping only on hover/focus left every closed tooltip's off-screen
  // portion contributing to document.scrollWidth, which mobile browsers
  // can pan/rubber-band into even though nothing is visibly there. Running
  // the same clamp on mount and on resize (not just on show) keeps the
  // bubble's box fully inside the viewport at all times, which is what
  // actually removes the extra scrollable width rather than just hiding
  // its symptom on interaction.
  useLayoutEffect(() => {
    clampPosition();
    window.addEventListener("resize", clampPosition);
    return () => window.removeEventListener("resize", clampPosition);
  }, [clampPosition]);

  return (
    <span
      ref={triggerRef}
      className="has-tooltip"
      tabIndex={0}
      onMouseEnter={clampPosition}
      onFocus={clampPosition}
    >
      {children}
      <span ref={bubbleRef} className="has-tooltip__bubble" role="tooltip">
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
  const id = useId();

  return (
    <>
      {/* Desktop/tablet: the pill group below. Both markups render always -
          swiss.css swaps which one is visible by breakpoint (the same
          pattern AppShell uses for its drawer vs. sidebar nav) so there's
          no resize-driven remount or layout flash. */}
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

      {/* Mobile: a native dropdown with a visible title to its left - a
          five-option pill group like Rankings' Metric selector has no room
          to sit un-scrolled on a phone, and horizontal-scrolling a filter
          buries options the pill group otherwise shows all at once. */}
      <div className="segmented-select">
        <label className="segmented-select__label" htmlFor={id}>
          {label}
        </label>
        <select
          id={id}
          className="segmented-select__input"
          value={value}
          onChange={(event) => onChange(event.target.value as T)}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}
