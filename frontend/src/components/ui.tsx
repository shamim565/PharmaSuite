"use client";

import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api";

/* ─────────────────────────────── Card ──────────────────────────────── */

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        {subtitle ? <p className="text-xs text-slate-500">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

/* ─────────────────────────────── Button ────────────────────────────── */

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
};

const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50 select-none";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "bg-primary-600 text-white hover:bg-primary-700 shadow-sm shadow-primary-200 focus-visible:ring-2 focus-visible:ring-primary-400",
  secondary:
    "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-slate-400",
  danger:
    "bg-danger-600 text-white hover:bg-danger-700 shadow-sm shadow-danger-200 focus-visible:ring-2 focus-visible:ring-danger-400",
  ghost: "text-slate-600 hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-slate-300",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "min-h-[36px] px-3 py-1.5 text-xs",
  md: "min-h-[44px] px-4 py-2.5 text-sm",
  lg: "min-h-[52px] px-5 py-3 text-base",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  loading,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`${buttonBase} ${buttonVariants[variant]} ${buttonSizes[size]} ${className}`}
    >
      {loading ? (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent opacity-70" />
      ) : null}
      {children}
    </button>
  );
}

/* ─────────────────────── ConfirmButton (two-tap) ────────────────────── */

export function ConfirmButton({
  onConfirm,
  confirmLabel = "Confirm?",
  children,
  timeoutMs = 4000,
  ...props
}: ButtonProps & {
  onConfirm: () => void;
  confirmLabel?: string;
  timeoutMs?: number;
}) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), timeoutMs);
    return () => clearTimeout(timer);
  }, [armed, timeoutMs]);

  return (
    <Button
      {...props}
      variant={armed ? "danger" : props.variant}
      onClick={(event) => {
        if (armed) {
          setArmed(false);
          onConfirm();
        } else {
          setArmed(true);
        }
        props.onClick?.(event);
      }}
    >
      {armed ? confirmLabel : children}
    </Button>
  );
}

/* ─────────────────────────────── Field ─────────────────────────────── */

export function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string | null;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      {children}
      {hint && !error ? <span className="block text-xs text-slate-500">{hint}</span> : null}
      {error ? <span className="block text-xs text-danger-600">{error}</span> : null}
    </label>
  );
}

/* ─────────────────────────────── Input ─────────────────────────────── */

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-base leading-tight outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-100 disabled:bg-slate-50 disabled:text-slate-500 ${props.className ?? ""}`}
    />
  );
}

/* ─────────────────────────────── Select ────────────────────────────── */

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full appearance-none rounded-xl border border-slate-300 bg-white px-3 py-3 text-base leading-tight outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-100 disabled:bg-slate-50 disabled:text-slate-500 ${props.className ?? ""}`}
    />
  );
}

/* ─────────────────────────────── Textarea ───────────────────────────── */

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-base leading-snug outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-100 disabled:bg-slate-50 ${props.className ?? ""}`}
    />
  );
}

/* ─────────────────────────────── Badge ─────────────────────────────── */

export function Badge({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: "slate" | "green" | "amber" | "rose" | "blue" | "purple";
}) {
  const tones: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-primary-100 text-primary-700",
    amber: "bg-amber-100 text-amber-700",
    rose: "bg-danger-100 text-danger-700",
    blue: "bg-sky-100 text-sky-700",
    purple: "bg-violet-100 text-violet-700",
  };
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

/* ─────────────────────────────── Spinner ───────────────────────────── */

export function Spinner({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-slate-500">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-primary-600" />
      {label}
    </div>
  );
}

/* ─────────────────────────── PageSpinner ───────────────────────────── */

export function PageSpinner({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-sm text-slate-500">
      <span className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-primary-600" />
      {label}
    </div>
  );
}

/* ─────────────────────────── ErrorBanner ───────────────────────────── */

export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof ApiError ? error.message : "Something went wrong";
  return (
    <div className="rounded-xl border border-danger-200 bg-danger-50 px-4 py-3 text-sm text-danger-700">
      {message}
    </div>
  );
}

/* ─────────────────────────── EmptyState ───────────────────────────── */

export function EmptyState({
  message,
  icon,
  action,
}: {
  message: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 p-10 text-center">
      {icon ? <span className="text-4xl opacity-30">{icon}</span> : null}
      <p className="text-sm text-slate-500">{message}</p>
      {action}
    </div>
  );
}

/* ──────────────────────────── Toast system ─────────────────────────── */

type ToastVariant = "success" | "error" | "info";

type Toast = {
  id: number;
  message: string;
  variant: ToastVariant;
};

type ToastContextValue = {
  toast: (message: string, variant?: ToastVariant) => void;
};

const ToastContext = createContext<ToastContextValue>({ toast: () => undefined });

export function useToast() {
  return useContext(ToastContext);
}

let _toastCounter = 0;
let _externalToast: ((message: string, variant: ToastVariant) => void) | null = null;

/**
 * Emit a toast from anywhere — including non-React code such as the global
 * React Query mutation cache. The mounted ToastProvider subscribes to this.
 */
export function pushToast(message: string, variant: ToastVariant = "success") {
  _externalToast?.(message, variant);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, variant: ToastVariant = "success") => {
    const id = ++_toastCounter;
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3500);
  }, []);

  useEffect(() => {
    _externalToast = toast;
    return () => {
      _externalToast = null;
    };
  }, [toast]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const variantStyles: Record<ToastVariant, string> = {
    success: "bg-primary-700 text-white",
    error: "bg-danger-700 text-white",
    info: "bg-slate-800 text-white",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed left-0 right-0 z-[200] flex flex-col items-center gap-2 px-4 pb-20 bottom-0 lg:right-4 lg:left-auto lg:items-end lg:pb-4"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex w-full max-w-sm items-center gap-3 rounded-xl px-4 py-3 shadow-xl ${variantStyles[t.variant]}`}
          >
            <span className="flex-1 text-sm font-medium">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="rounded-full p-0.5 opacity-70 hover:opacity-100"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/* ──────────────────────────── Bottom Sheet ─────────────────────────── */

type SheetProps = {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "full";
};

export function Sheet({ open, onClose, title, children, size = "md" }: SheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  const maxW =
    size === "sm"
      ? "max-w-sm"
      : size === "lg"
        ? "max-w-2xl"
        : size === "full"
          ? "max-w-full"
          : "max-w-lg";

  return (
    <div className="fixed inset-0 z-[100]">
      <div className="absolute inset-0 bg-slate-900/50" onClick={onClose} />
      <div className="absolute inset-x-0 bottom-0 lg:inset-0 lg:flex lg:items-center lg:justify-center lg:p-4">
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          className={`relative w-full ${maxW} rounded-t-2xl bg-white shadow-2xl lg:rounded-2xl`}
          style={{ maxHeight: "90dvh" }}
        >
          {/* Handle (mobile only) */}
          <div className="mx-auto mt-3 h-1 w-10 rounded-full bg-slate-300 lg:hidden" />
          {title ? (
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <h3 className="text-base font-semibold text-slate-800">{title}</h3>
              <button
                onClick={onClose}
                className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
          ) : (
            <button
              onClick={onClose}
              className="absolute right-3 top-3 rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          )}
          <div className="overflow-y-auto" style={{ maxHeight: "calc(90dvh - 3.5rem)" }}>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────────── DataTable ────────────────────────────── */

type Column<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  hideMobile?: boolean;
};

type DataTableProps<T> = {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  cardRow?: (row: T) => ReactNode;
  onRowClick?: (row: T) => void;
  loading?: boolean;
  empty?: string;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  cardRow,
  onRowClick,
  loading,
  empty = "No records found.",
}: DataTableProps<T>) {
  if (loading) return <Spinner />;
  if (!rows.length) return <EmptyState message={empty} />;

  return (
    <>
      {/* Mobile: card list */}
      <div className="divide-y divide-slate-100 md:hidden">
        {rows.map((row) => {
          const keyboardProps = onRowClick
            ? {
                tabIndex: 0,
                onKeyDown: (e: React.KeyboardEvent) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onRowClick(row);
                  }
                },
              }
            : {};
          return cardRow ? (
            <div
              key={rowKey(row)}
              onClick={() => onRowClick?.(row)}
              className={onRowClick ? "cursor-pointer hover:bg-slate-50 active:bg-slate-100" : ""}
              {...keyboardProps}
            >
              {cardRow(row)}
            </div>
          ) : (
            <div
              key={rowKey(row)}
              onClick={() => onRowClick?.(row)}
              className={`px-4 py-3 ${onRowClick ? "cursor-pointer hover:bg-slate-50" : ""}`}
              {...keyboardProps}
            >
              {columns.map((col) => (
                <div key={col.key} className="flex items-start justify-between gap-2 py-0.5">
                  <span className="min-w-[90px] shrink-0 text-xs text-slate-500">{col.header}</span>
                  <span className="text-right text-sm text-slate-800">{col.cell(row)}</span>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {/* Desktop: table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={() => onRowClick?.(row)}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                className={`transition ${onRowClick ? "cursor-pointer hover:bg-slate-50 active:bg-slate-100" : ""}`}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3">
                    {col.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ──────────────────────────── Pagination ───────────────────────────── */

export function Pagination({
  page,
  hasPrevious,
  hasNext,
  onChange,
}: {
  page: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onChange: (page: number) => void;
}) {
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm">
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded px-2 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        disabled={!hasPrevious}
        onClick={() => onChange(page - 1)}
      >
        <ChevronLeft aria-hidden size={14} />
        Previous
      </button>
      <span className="text-xs text-slate-500">Page {page}</span>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded px-2 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        disabled={!hasNext}
        onClick={() => onChange(page + 1)}
      >
        Next
        <ChevronRight aria-hidden size={14} />
      </button>
    </div>
  );
}

/* ──────────────────────────── Tabs ─────────────────────────────────── */

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  className = "",
}: {
  tabs: readonly T[];
  active: T;
  onChange: (tab: T) => void;
  className?: string;
}) {
  return (
    <div role="tablist" className={`flex flex-wrap gap-2 ${className}`}>
      {tabs.map((tab) => (
        <button
          key={tab}
          type="button"
          role="tab"
          aria-selected={active === tab}
          onClick={() => onChange(tab)}
          className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
            active === tab ? "bg-primary-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
          }`}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}

/* ──────────────────────────── StickyBar ────────────────────────────── */

export function StickyBar({ children }: { children: ReactNode }) {
  return (
    <div className="sticky bottom-[var(--bottom-nav-height)] z-10 -mx-4 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur-sm lg:bottom-0 lg:mx-0 lg:rounded-b-xl">
      {children}
    </div>
  );
}

/* ──────────────────────────── Divider ──────────────────────────────── */

export function Divider({ label }: { label?: string }) {
  if (!label) return <hr className="border-slate-100" />;
  return (
    <div className="relative flex items-center gap-3">
      <hr className="flex-1 border-slate-200" />
      <span className="text-xs text-slate-500">{label}</span>
      <hr className="flex-1 border-slate-200" />
    </div>
  );
}
