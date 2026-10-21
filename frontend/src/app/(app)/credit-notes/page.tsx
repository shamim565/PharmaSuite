"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmButton,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Pagination,
  Select,
  Spinner,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type { Branch, Paginated, StockAdjustment, Supplier, SupplierCreditNote } from "@/lib/types";

const emptyForm = {
  branch: "",
  supplier: "",
  business_date: "",
  amount: "",
  reason_code: "EXPIRY_RETURN",
  reference: "",
  notes: "",
  adjustment: "",
};

function statusTone(status: SupplierCreditNote["status"]): "slate" | "green" | "rose" {
  return status === "OPEN" ? "slate" : status === "SETTLED" ? "green" : "rose";
}

export default function CreditNotesPage() {
  const { user, hasPerm } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyForm, branch: user?.default_branch_id ?? "" });
  const [cancelFor, setCancelFor] = useState<SupplierCreditNote | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const debouncedSearch = useDebouncedValue(search);

  const params = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) params.set("search", debouncedSearch);
  if (statusFilter) params.set("status", statusFilter);

  const notesQuery = useQuery({
    queryKey: ["supplier-credit-notes", debouncedSearch, statusFilter, page],
    queryFn: () =>
      api.get<Paginated<SupplierCreditNote>>(`/supplier-credit-notes/?${params.toString()}`),
  });
  const suppliersQuery = useQuery({
    queryKey: ["suppliers", "select"],
    queryFn: () => api.get<Paginated<Supplier>>("/suppliers/?page_size=200&is_active=true"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });
  const expiryAdjustmentsQuery = useQuery({
    queryKey: ["adjustments", "expiry-write-off"],
    queryFn: () =>
      api.get<Paginated<StockAdjustment>>(
        "/inventory/adjustments/?reason_code=EXPIRY_WRITE_OFF&status=POSTED&page_size=200",
      ),
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["supplier-credit-notes"] });
    queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    queryClient.invalidateQueries({ queryKey: ["adjustments"] });
  };

  const createMutation = useMutation({
    meta: { successMessage: "Supplier credit note created" },
    mutationFn: () =>
      api.postWithKey<SupplierCreditNote>(
        "/supplier-credit-notes/",
        {
          ...form,
          business_date: form.business_date || undefined,
          amount: form.amount,
          adjustment: form.adjustment || null,
        },
        `scn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      ),
    onSuccess: () => {
      setForm({ ...emptyForm, branch: user?.default_branch_id ?? "" });
      setShowForm(false);
      invalidateAll();
    },
  });

  const settleMutation = useMutation({
    meta: { successMessage: "Credit note settled — payable reduced" },
    mutationFn: (id: string) =>
      api.post<SupplierCreditNote>(`/supplier-credit-notes/${id}/settle/`, {}),
    onSuccess: invalidateAll,
  });

  const cancelMutation = useMutation({
    meta: { successMessage: "Credit note cancelled" },
    mutationFn: () =>
      api.post(`/supplier-credit-notes/${cancelFor?.id}/cancel/`, {
        reason: cancelReason || "Cancelled from credit note register",
      }),
    onSuccess: () => {
      setCancelFor(null);
      setCancelReason("");
      invalidateAll();
    },
  });

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Supplier credit notes</h1>
        {hasPerm("PURCHASE_CONFIRM") ? (
          <Button size="sm" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Close" : "New credit note"}
          </Button>
        ) : null}
      </div>

      {showForm ? (
        <Card>
          <CardHeader
            title="New supplier credit note"
            subtitle="Settling reduces the supplier payable through the ledger."
          />
          <form
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              createMutation.mutate();
            }}
            className="space-y-3 p-4"
          >
            <ErrorBanner error={createMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Field label="Supplier" error={fieldError("supplier")}>
                <Select
                  value={form.supplier}
                  onChange={(e) => setForm({ ...form, supplier: e.target.value })}
                  required
                >
                  <option value="">Select…</option>
                  {suppliersQuery.data?.results.map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>
                      {supplier.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Branch" error={fieldError("branch")}>
                <Select
                  value={form.branch}
                  onChange={(e) => setForm({ ...form, branch: e.target.value })}
                  required
                >
                  <option value="">Select…</option>
                  {branchesQuery.data?.results.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Date" error={fieldError("business_date")}>
                <Input
                  type="date"
                  value={form.business_date}
                  onChange={(e) => setForm({ ...form, business_date: e.target.value })}
                  required
                />
              </Field>
              <Field label="Amount" error={fieldError("amount")}>
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  required
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Field label="Reason">
                <Select
                  value={form.reason_code}
                  onChange={(e) => setForm({ ...form, reason_code: e.target.value })}
                >
                  <option value="EXPIRY_RETURN">Expired goods return</option>
                  <option value="DAMAGED_RETURN">Damaged goods return</option>
                  <option value="PRICE_ADJUSTMENT">Price adjustment</option>
                  <option value="OTHER">Other</option>
                </Select>
              </Field>
              <Field label="Supplier CN #">
                <Input
                  value={form.reference}
                  onChange={(e) => setForm({ ...form, reference: e.target.value })}
                />
              </Field>
              <div className="col-span-2">
                <Field label="Expiry write-off (optional)">
                  <Select
                    value={form.adjustment}
                    onChange={(e) => setForm({ ...form, adjustment: e.target.value })}
                  >
                    <option value="">None</option>
                    {expiryAdjustmentsQuery.data?.results.map((adjustment) => (
                      <option key={adjustment.id} value={adjustment.id}>
                        {adjustment.number ?? adjustment.id.slice(0, 8)} ·{" "}
                        {formatDate(adjustment.business_date)} ·{" "}
                        {formatMoney(adjustment.total_value)}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            </div>
            <Field label="Notes">
              <Input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </Field>
            <Button type="submit" className="w-full lg:w-auto" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Create credit note"}
            </Button>
          </form>
        </Card>
      ) : null}

      {cancelFor ? (
        <Card>
          <CardHeader
            title={`Cancel credit note ${cancelFor.number ?? ""}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setCancelFor(null)}>
                Close
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={cancelMutation.error} />
            <Field label="Reason">
              <Input value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} />
            </Field>
            <Button
              variant="danger"
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending || !cancelReason}
            >
              {cancelMutation.isPending ? "Cancelling…" : "Cancel credit note"}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Credit note register"
          subtitle={notesQuery.data ? `${notesQuery.data.count} note(s)` : undefined}
          action={
            <div className="flex flex-wrap gap-2">
              <Select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="w-40"
                aria-label="Filter by status"
              >
                <option value="">All statuses</option>
                <option value="OPEN">Open</option>
                <option value="SETTLED">Settled</option>
                <option value="CANCELLED">Cancelled</option>
              </Select>
              <Input
                placeholder="Search number, supplier…"
                aria-label="Search credit notes"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-56"
              />
            </div>
          }
        />
        <ErrorBanner error={notesQuery.error} />
        {notesQuery.isLoading ? (
          <Spinner />
        ) : !notesQuery.data || notesQuery.data.results.length === 0 ? (
          <EmptyState message="No supplier credit notes yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {notesQuery.data.results.map((note) => (
              <li key={note.id} className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">
                      {note.number ?? `Draft ${note.id.slice(0, 8)}`}{" "}
                      {note.reference ? (
                        <span className="text-xs text-slate-500">· supplier #{note.reference}</span>
                      ) : null}
                    </p>
                    <p className="text-xs text-slate-500">
                      {note.supplier_name} · {formatDate(note.business_date)} · {note.reason_code}
                      {note.adjustment_number ? ` · from adjustment ${note.adjustment_number}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-primary-700">
                      {formatMoney(note.amount)}
                    </span>
                    <Badge tone={statusTone(note.status)}>{note.status}</Badge>
                  </div>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-slate-500">
                    {note.status === "OPEN" && note.days_open !== null
                      ? `Open for ${note.days_open} day(s)`
                      : note.status === "SETTLED"
                        ? `Settled ${formatDate(note.settled_at ?? "")} by ${note.settled_by_name || "—"}`
                        : note.cancel_reason
                          ? `Cancelled: ${note.cancel_reason}`
                          : "Cancelled"}
                  </p>
                  {note.status === "OPEN" && hasPerm("PURCHASE_CONFIRM") ? (
                    <div className="flex gap-2">
                      <ConfirmButton
                        size="sm"
                        confirmLabel="Settle & reduce payable?"
                        onConfirm={() => settleMutation.mutate(note.id)}
                        disabled={settleMutation.isPending}
                      >
                        Settle
                      </ConfirmButton>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setCancelFor(note);
                          setCancelReason("");
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
        {notesQuery.data && notesQuery.data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(notesQuery.data.previous)}
            hasNext={Boolean(notesQuery.data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
