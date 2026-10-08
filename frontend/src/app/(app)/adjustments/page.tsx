"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, ConfirmButton, EmptyState, ErrorBanner, Field, Input, Pagination, Select, Spinner } from "@/components/ui";
import { AttachmentPanel } from "@/components/attachments";
import { MedicineCombobox } from "@/components/medicine-combobox";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type { Branch, MedicineBatch, Paginated, StockAdjustment } from "@/lib/types";

const emptyForm = {
  branch: "",
  adjustment_type: "DECREASE",
  reason_code: "DAMAGE",
  notes: "",
  medicine: "",
  batch: "",
  qty: "",
  pool: "SALEABLE",
  target_pool: "",
  unit_cost: "",
};

const REASONS = [
  ["DATA_CORRECTION", "Data correction"],
  ["COUNT_VARIANCE", "Count variance"],
  ["DAMAGE", "Damage"],
  ["EXPIRY_WRITE_OFF", "Expiry write-off"],
  ["FOUND_STOCK", "Found stock"],
  ["PROMO_REPLENISH", "Promotional replenishment"],
  ["RECALL_DISPOSAL", "Recall disposal"],
] as const;

function statusTone(status: StockAdjustment["status"]): "green" | "amber" | "rose" | "slate" {
  if (status === "POSTED") return "green";
  if (status === "PENDING_APPROVAL") return "amber";
  if (status === "REJECTED" || status === "REVERSED") return "rose";
  return "slate";
}

export default function AdjustmentsPage() {
  const queryClient = useQueryClient();
  const { user, hasPerm } = useAuth();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [rejectFor, setRejectFor] = useState<StockAdjustment | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [reverseFor, setReverseFor] = useState<StockAdjustment | null>(null);
  const [reverseReason, setReverseReason] = useState("");
  const [filesFor, setFilesFor] = useState<StockAdjustment | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  const adjustmentParams = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) adjustmentParams.set("search", debouncedSearch);

  const adjustmentsQuery = useQuery({
    queryKey: ["adjustments", debouncedSearch, page],
    queryFn: () =>
      api.get<Paginated<StockAdjustment>>(`/inventory/adjustments/?${adjustmentParams.toString()}`),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });
  const batchesQuery = useQuery({
    queryKey: ["batches", "select", form.medicine, form.branch],
    queryFn: () =>
      api.get<Paginated<MedicineBatch>>(
        `/batches/?page_size=100&medicine=${form.medicine}${form.branch ? `&branch=${form.branch}` : ""}`,
      ),
    enabled: Boolean(form.medicine),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["adjustments"] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["batches"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const createMutation = useMutation({
    meta: { successMessage: "Adjustment posted" },
    mutationFn: () =>
      api.post<StockAdjustment>("/inventory/adjustments/", {
        branch: form.branch,
        adjustment_type: form.adjustment_type,
        reason_code: form.reason_code,
        notes: form.notes,
        items: [
          {
            medicine: form.medicine,
            batch: form.batch,
            qty: form.qty,
            pool: form.pool,
            target_pool: form.adjustment_type === "DECREASE" && form.target_pool ? form.target_pool : null,
            unit_cost: form.unit_cost || null,
          },
        ],
      }),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      invalidate();
    },
  });

  const actionMutation = useMutation({
    meta: {
      successMessage: (variables: { action: string }) => {
        switch (variables.action) {
          case "approve":
            return "Adjustment approved";
          case "reject":
            return "Adjustment rejected";
          case "reverse":
            return "Adjustment reversed";
          default:
            return "Adjustment updated";
        }
      },
    },
    mutationFn: ({ id, action, reason }: { id: string; action: string; reason?: string }) =>
      api.post(`/inventory/adjustments/${id}/${action}/`, reason ? { reason } : {}),
    onSuccess: () => {
      setRejectFor(null);
      setRejectReason("");
      setReverseFor(null);
      setReverseReason("");
      invalidate();
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate();
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  const selectedBatch = batchesQuery.data?.results.find((batch) => batch.id === form.batch);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Stock adjustments</h1>
        {hasPerm("STOCK_ADJUST") ? (
          <Button size="sm" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Close" : "New adjustment"}
          </Button>
        ) : null}
      </div>

      {showForm && hasPerm("STOCK_ADJUST") ? (
        <Card>
          <CardHeader
            title="New adjustment"
            subtitle="Adjustments above the approval threshold require a second approver."
          />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error} />
            </div>
            <Field label="Branch" error={fieldError("branch")}>
              <Select value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })} required>
                <option value="">Select…</option>
                {branchesQuery.data?.results.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Direction" error={fieldError("adjustment_type")}>
              <Select
                value={form.adjustment_type}
                onChange={(e) => setForm({ ...form, adjustment_type: e.target.value })}
              >
                <option value="DECREASE">Decrease (loss / move)</option>
                <option value="INCREASE">Increase (found stock)</option>
              </Select>
            </Field>
            <Field label="Reason" error={fieldError("reason_code")}>
              <Select value={form.reason_code} onChange={(e) => setForm({ ...form, reason_code: e.target.value })}>
                {REASONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="col-span-2">
              <Field label="Medicine" error={fieldError("medicine")}>
                <MedicineCombobox
                  value={form.medicine}
                  onChange={(id) => setForm((current) => ({ ...current, medicine: id, batch: "" }))}
                />
              </Field>
            </div>
            <div className="col-span-2">
              <Field label="Batch" error={fieldError("batch")}>
                <Select
                  value={form.batch}
                  onChange={(e) => setForm({ ...form, batch: e.target.value })}
                  required
                  disabled={!form.medicine}
                >
                  <option value="">Select…</option>
                  {batchesQuery.data?.results.map((batch) => (
                    <option key={batch.id} value={batch.id}>
                      {batch.batch_number} · qty {formatQty(batch.qty_on_hand)} · exp {batch.expiry_date ? formatDate(batch.expiry_date) : "—"}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Field label="Quantity" error={fieldError("qty")}>
              <Input
                type="number"
                step="0.001"
                min="0.001"
                value={form.qty}
                onChange={(e) => setForm({ ...form, qty: e.target.value })}
                required
              />
            </Field>
            <Field label="Unit cost (optional)" error={fieldError("unit_cost")}>
              <Input
                type="number"
                step="0.0001"
                min="0"
                placeholder={selectedBatch ? selectedBatch.unit_cost : "batch cost"}
                value={form.unit_cost}
                onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
              />
            </Field>
            <Field label="From pool">
              <Select value={form.pool} onChange={(e) => setForm({ ...form, pool: e.target.value })}>
                <option value="SALEABLE">Saleable</option>
                <option value="PROMO">Promotional</option>
                <option value="QUARANTINE">Quarantine</option>
              </Select>
            </Field>
            {form.adjustment_type === "DECREASE" ? (
              <Field label="Move to pool (optional)">
                <Select
                  value={form.target_pool}
                  onChange={(e) => setForm({ ...form, target_pool: e.target.value })}
                >
                  <option value="">— (loss)</option>
                  <option value="QUARANTINE">Quarantine</option>
                  <option value="PROMO">Promotional</option>
                  <option value="SALEABLE">Saleable</option>
                </Select>
              </Field>
            ) : null}
            <div className="col-span-2 lg:col-span-4">
              <Field label="Notes" error={fieldError("notes")}>
                <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </Field>
            </div>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Post adjustment"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      {rejectFor ? (
        <Card>
          <CardHeader
            title={`Reject adjustment ${rejectFor.number ?? ""}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setRejectFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={actionMutation.error} />
            <Field label="Reason">
              <Input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
            </Field>
            <Button
              variant="danger"
              disabled={actionMutation.isPending || !rejectReason}
              onClick={() => actionMutation.mutate({ id: rejectFor.id, action: "reject", reason: rejectReason })}
            >
              Reject adjustment
            </Button>
          </div>
        </Card>
      ) : null}

      {reverseFor ? (
        <Card>
          <CardHeader
            title={`Reverse adjustment ${reverseFor.number ?? ""}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setReverseFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={actionMutation.error} />
            <p className="text-sm text-slate-600">
              This posts an opposite stock movement. Stock currently adjusted will be restored.
            </p>
            <Field label="Reason">
              <Input value={reverseReason} onChange={(e) => setReverseReason(e.target.value)} />
            </Field>
            <Button
              variant="danger"
              disabled={actionMutation.isPending || !reverseReason}
              onClick={() => actionMutation.mutate({ id: reverseFor.id, action: "reverse", reason: reverseReason })}
            >
              Reverse adjustment
            </Button>
          </div>
        </Card>
      ) : null}

      {filesFor ? (
        <Card>
          <CardHeader
            title={`Evidence — ${filesFor.number ?? "adjustment"}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setFilesFor(null)}>
                Close
              </Button>
            }
          />
          <div className="p-4">
            <AttachmentPanel ownerType="STOCK_ADJUSTMENT" ownerId={filesFor.id} title="Evidence" />
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Adjustment register"
          subtitle={adjustmentsQuery.data ? `${adjustmentsQuery.data.count} adjustment(s)` : undefined}
          action={
            <Input
              placeholder="Search medicine, notes…"
              aria-label="Search adjustments"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-52"
            />
          }
        />
        <ErrorBanner error={adjustmentsQuery.error} />
        {adjustmentsQuery.isLoading ? (
          <Spinner />
        ) : !adjustmentsQuery.data || adjustmentsQuery.data.results.length === 0 ? (
          <EmptyState message="No adjustments yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {adjustmentsQuery.data.results.map((adjustment) => {
              const canApprove =
                adjustment.status === "PENDING_APPROVAL" &&
                hasPerm("STOCK_ADJUST") &&
                adjustment.requested_by_name !== user?.full_name;
              return (
                <li key={adjustment.id} className="space-y-2 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium">
                        {adjustment.number ?? "Pending"}{" "}
                        <span className="text-xs text-slate-500">
                          {adjustment.items.map((item) => item.medicine_name).join(", ")}
                        </span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatDate(adjustment.business_date)} · {adjustment.adjustment_type} ·{" "}
                        {adjustment.reason_code.replace(/_/g, " ").toLowerCase()} · value {formatMoney(adjustment.total_value)}
                      </p>
                      <p className="text-xs text-slate-500">
                        Requested by {adjustment.requested_by_name || "—"}
                        {adjustment.approved_by_name ? ` · approved by ${adjustment.approved_by_name}` : ""}
                        {adjustment.rejection_reason ? ` · rejected: ${adjustment.rejection_reason}` : ""}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={statusTone(adjustment.status)}>{adjustment.status.replace("_", " ")}</Badge>
                      {canApprove ? (
                        <>
                          <ConfirmButton
                            size="sm"
                            confirmLabel="Confirm approve?"
                            disabled={actionMutation.isPending}
                            onConfirm={() => actionMutation.mutate({ id: adjustment.id, action: "approve" })}
                          >
                            Approve
                          </ConfirmButton>
                          <Button size="sm" variant="ghost" onClick={() => setRejectFor(adjustment)}>
                            Reject
                          </Button>
                        </>
                      ) : null}
                      <Button size="sm" variant="secondary" onClick={() => setFilesFor(adjustment)}>Files</Button>
                      {adjustment.status === "POSTED" && hasPerm("STOCK_ADJUST") ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setReverseFor(adjustment);
                            setReverseReason("");
                          }}
                          disabled={actionMutation.isPending}
                        >
                          Reverse
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <ul className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    {adjustment.items.map((item) => (
                      <li key={item.id}>
                        {item.medicine_name} ({item.medicine_code}) · batch {item.batch_number} · qty {formatQty(item.qty)} ·{" "}
                        {item.pool}
                        {item.target_pool ? ` → ${item.target_pool}` : ""} @ {formatMoney(item.unit_cost)}
                      </li>
                    ))}
                  </ul>
                </li>
              );
            })}
          </ul>
        )}
        {adjustmentsQuery.data && adjustmentsQuery.data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(adjustmentsQuery.data.previous)}
            hasNext={Boolean(adjustmentsQuery.data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
