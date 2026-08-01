/** Display helpers.
 *
 * The backend returns null for "no data" rather than 0, and that difference
 * is meaningful — a post with null reach was never measured, a post with 0
 * reach was. Every formatter here preserves it as an em-dash.
 */

const EM_DASH = "—";

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return EM_DASH;
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatPercent(
  value: number | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) return EM_DASH;
  return `${value.toFixed(digits)}%`;
}

export function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return EM_DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function formatSigned(value: number | null | undefined): string {
  if (value === null || value === undefined) return EM_DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${new Intl.NumberFormat("en-US").format(value)}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return EM_DASH;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return EM_DASH;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return EM_DASH;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return EM_DASH;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** Shorten a caption for a table cell without cutting mid-word where possible. */
export function truncate(text: string | null | undefined, max = 60): string {
  if (!text) return EM_DASH;
  if (text.length <= max) return text;
  const clipped = text.slice(0, max);
  const lastSpace = clipped.lastIndexOf(" ");
  return `${lastSpace > max * 0.6 ? clipped.slice(0, lastSpace) : clipped}…`;
}

/** "IMAGE" -> "Image", "CAROUSEL_ALBUM" -> "Carousel album". */
export function formatMediaType(value: string): string {
  const words = value.toLowerCase().split("_");
  return words
    .map((word, index) => (index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word))
    .join(" ");
}

export { EM_DASH };
