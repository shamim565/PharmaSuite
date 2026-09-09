/**
 * Central display formatting for the ERP.
 *
 * Every money, quantity, and date value rendered in the UI must go through
 * these helpers so the whole app stays consistent (BDT currency symbol,
 * South-Asian digit grouping, unambiguous dates).
 */

const moneyFormatter = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const qtyFormatter = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 3,
});

/**
 * Format a money value as `৳ 1,23,456.78`. Returns "—" for missing values.
 * Accepts the decimal strings the API returns.
 */
export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return String(value);
  return `৳ ${moneyFormatter.format(n)}`;
}

/** Same as formatMoney but without the currency symbol (for table cells that already have a ৳ column header). */
export function formatAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return String(value);
  return moneyFormatter.format(n);
}

/**
 * Format a quantity with up to 3 decimal places, trimming trailing zeros
 * (e.g. 12.5, 12.001, 0.5). Returns "—" for missing values.
 */
export function formatQty(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return String(value);
  return qtyFormatter.format(n);
}

/**
 * Format a date as `11 Oct 2026`. Date-only strings (YYYY-MM-DD) are parsed
 * as local dates so they never shift a day due to timezone conversion.
 * Returns "—" for missing values.
 */
export function formatDate(value: string | null | undefined): string {
  const date = parseDate(value);
  if (!date) return value ? String(value) : "—";
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/**
 * Format a timestamp as `11 Oct 2026, 14:30` (24-hour, local time).
 * Returns "—" for missing values.
 */
export function formatDateTime(value: string | null | undefined): string {
  const date = parseDate(value);
  if (!date) return value ? String(value) : "—";
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    const date = new Date(year, month - 1, day);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}
