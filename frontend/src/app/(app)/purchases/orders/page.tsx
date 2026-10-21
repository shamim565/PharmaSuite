"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Pagination,
  Select,
  Spinner,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type { Branch, Medicine, Paginated, Purchase, PurchaseOrder, Supplier } from "@/lib/types";

type DraftRow = {
  key: number;
  medicine: string;
  qty_ordered: string;
  unit_cost: string;
  line_discount: string;
  vat_rate: string;
};

const newRow = (key: number): DraftRow => ({
  key,
  medicine: "",
  qty_ordered: "",
  unit_cost: "",
  line_discount: "0",
  vat_rate: "15",
});

const emptyForm = {
  supplier: "",
  branch: "",
  business_date: "",
  expected_delivery_date: "",
  notes: "",
};

const STATUS_TONES: Record<PurchaseOrder["status"], "slate" | "blue" | "green" | "amber" | "rose"> =
  {
    DRAFT: "slate",
    SUBMITTED: "blue",
    APPROVED: "green",
    PARTIALLY_RECEIVED: "amber",
    FULLY_RECEIVED: "green",
    CANCELLED: "rose",
  };

function poTone(status: PurchaseOrder["status"]) {
  return STATUS_TONES[status];
}

export default function PurchaseOrdersPage() {
  const { user, hasPerm } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyForm, branch: user?.default_branch_id ?? "" });
  const [rows, setRows] = useState<DraftRow[]>([newRow(1)]);
  const [rowSeq, setRowSeq] = useState(2);
  const debouncedSearch = useDebouncedValue(search);

  const [convertFor, setConvertFor] = useState<PurchaseOrder | null>(null);
  const [convertInvoiceNumber, setConvertInvoiceNumber] = useState("");
  const [convertInvoiceDate, setConvertInvoiceDate] = useState("");
  const [cancelFor, setCancelFor] = useState<PurchaseOrder | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  const params = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) params.set("search", debouncedSearch);
  if (statusFilter) params.set("status", statusFilter);

  const ordersQuery = useQuery({
    queryKey: ["purchase-orders", debouncedSearch, statusFilter, page],
    queryFn: () => api.get<Paginated<PurchaseOrder>>(`/purchase-orders/?${params.toString()}`),
  });
  const suppliersQuery = useQuery({
    queryKey: ["suppliers", "select"],
    queryFn: () => api.get<Paginated<Supplier>>("/suppliers/?page_size=200&is_active=true"),
  });
  const medicinesQuery = useQuery({
    queryKey: ["medicines", "select"],
    queryFn: () => api.get<Paginated<Medicine>>("/medicines/?page_size=200&is_active=true"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
    queryClient.invalidateQueries({ queryKey: ["purchases"] });
    queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    queryClient.invalidateQueries({ queryKey: ["batches"] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
  };

  const createMutation = useMutation({
    meta: { successMessage: "Purchase order created" },
    mutationFn: () =>
      api.postWithKey<PurchaseOrder>(
        "/purchase-orders/",
        {
          ...form,
          business_date: form.business_date || undefined,
          expected_delivery_date: form.expected_delivery_date || null,
          items: rows.map((row) => ({
            medicine: row.medicine,
            qty_ordered: row.qty_ordered,
            unit_cost: row.unit_cost || "0",
            line_discount: row.line_discount || "0",
            vat_rate: row.vat_rate || "15",
          })),
        },
        `po-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      ),
    onSuccess: () => {
      setForm({ ...emptyForm, branch: user?.default_branch_id ?? "" });
      setRows([newRow(1)]);
      setShowForm(false);
      invalidateAll();
    },
  });

  const submitMutation = useMutation({
    meta: { successMessage: "Purchase order submitted" },
    mutationFn: (id: string) => api.post<PurchaseOrder>(`/purchase-orders/${id}/submit/`, {}),
    onSuccess: invalidateAll,
  });

  const approveMutation = useMutation({
    meta: { successMessage: "Purchase order approved" },
    mutationFn: (id: string) => api.post<PurchaseOrder>(`/purchase-orders/${id}/approve/`, {}),
    onSuccess: invalidateAll,
  });

  const cancelMutation = useMutation({
    meta: { successMessage: "Purchase order cancelled" },
    mutationFn: () =>
      api.post(`/purchase-orders/${cancelFor?.id}/cancel/`, {
        reason: cancelReason || "Cancelled from purchase order register",
      }),
    onSuccess: () => {
      setCancelFor(null);
      setCancelReason("");
      invalidateAll();
    },
  });

  const convertMutation = useMutation({
    meta: { successMessage: "Purchase order received — GRN created" },
    mutationFn: () =>
      api.postWithKey<{ purchase_order: PurchaseOrder; purchase: Purchase }>(
        `/purchase-orders/${convertFor?.id}/convert-to-purchase/`,
        {
          supplier_invoice_number: convertInvoiceNumber,
          supplier_invoice_date: convertInvoiceDate || null,
        },
        `po-convert-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      ),
    onSuccess: () => {
      setConvertFor(null);
      setConvertInvoiceNumber("");
      setConvertInvoiceDate("");
      invalidateAll();
    },
  });

  const updateRow = (key: number, patch: Partial<DraftRow>) => {
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  const openConvert = (order: PurchaseOrder) => {
    setConvertFor(order);
    setConvertInvoiceNumber("");
    setConvertInvoiceDate("");
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Purchase orders</h1>
        {hasPerm("PURCHASE_MANAGE") ? (
          <Button size="sm" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Close" : "New purchase order"}
          </Button>
        ) : null}
      </div>

      {showForm ? (
        <Card>
          <CardHeader
            title="New purchase order"
            subtitle="Submit for approval, then convert to a purchase (GRN) when goods arrive."
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
              <Field label="Order date" error={fieldError("business_date")}>
                <Input
                  type="date"
                  value={form.business_date}
                  onChange={(e) => setForm({ ...form, business_date: e.target.value })}
                  required
                />
              </Field>
              <Field label="Expected delivery">
                <Input
                  type="date"
                  value={form.expected_delivery_date}
                  onChange={(e) => setForm({ ...form, expected_delivery_date: e.target.value })}
                />
              </Field>
            </div>

            <div className="space-y-2">
              {rows.map((row, index) => (
                <div
                  key={row.key}
                  className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 p-3 lg:grid-cols-6"
                >
                  <div className="col-span-2">
                    <Field label={`Medicine ${index + 1}`}>
                      <Select
                        value={row.medicine}
                        onChange={(e) => updateRow(row.key, { medicine: e.target.value })}
                        required
                      >
                        <option value="">Select…</option>
                        {medicinesQuery.data?.results.map((medicine) => (
                          <option key={medicine.id} value={medicine.id}>
                            {medicine.name} ({medicine.code})
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>
                  <Field label="Qty ordered">
                    <Input
                      type="number"
                      step="0.001"
                      min="0.001"
                      value={row.qty_ordered}
                      onChange={(e) => updateRow(row.key, { qty_ordered: e.target.value })}
                      required
                    />
                  </Field>
                  <Field label="Unit cost">
                    <Input
                      type="number"
                      step="0.0001"
                      min="0"
                      value={row.unit_cost}
                      onChange={(e) => updateRow(row.key, { unit_cost: e.target.value })}
                      required
                    />
                  </Field>
                  <Field label="Discount">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={row.line_discount}
                      onChange={(e) => updateRow(row.key, { line_discount: e.target.value })}
                    />
                  </Field>
                  <Field label="VAT %">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={row.vat_rate}
                      onChange={(e) => updateRow(row.key, { vat_rate: e.target.value })}
                    />
                  </Field>
                  <div className="flex items-end lg:col-span-6">
                    {rows.length > 1 ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          setRows((prev) => prev.filter((item) => item.key !== row.key))
                        }
                      >
                        Remove line
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => {
                  setRows((prev) => [...prev, newRow(rowSeq)]);
                  setRowSeq((seq) => seq + 1);
                }}
              >
                Add line
              </Button>
            </div>

            <Field label="Notes">
              <Input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </Field>

            <Button type="submit" className="w-full lg:w-auto" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Create purchase order"}
            </Button>
          </form>
        </Card>
      ) : null}

      {/* Convert to purchase (GRN) panel */}
      {convertFor ? (
        <Card>
          <CardHeader
            title={`Receive against ${convertFor.number}`}
            subtitle={`${convertFor.supplier_name} · ${formatMoney(convertFor.grand_total)} · creates a purchase (GRN) draft`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setConvertFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={convertMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              <Field label="Supplier invoice #">
                <Input
                  value={convertInvoiceNumber}
                  onChange={(e) => setConvertInvoiceNumber(e.target.value)}
                  required
                />
              </Field>
              <Field label="Supplier invoice date">
                <Input
                  type="date"
                  value={convertInvoiceDate}
                  onChange={(e) => setConvertInvoiceDate(e.target.value)}
                />
              </Field>
            </div>
            <p className="text-xs text-slate-500">
              A GRN draft is created with the pending quantities of this order. Confirm it from the
              Purchases register to post stock.
            </p>
            <Button
              onClick={() => convertMutation.mutate()}
              disabled={convertMutation.isPending || !convertInvoiceNumber}
            >
              {convertMutation.isPending ? "Creating GRN…" : "Create purchase (GRN)"}
            </Button>
          </div>
        </Card>
      ) : null}

      {cancelFor ? (
        <Card>
          <CardHeader
            title={`Cancel purchase order ${cancelFor.number ?? ""}`}
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
              {cancelMutation.isPending ? "Cancelling…" : "Cancel purchase order"}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Purchase order register"
          subtitle={ordersQuery.data ? `${ordersQuery.data.count} order(s)` : undefined}
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
                <option value="DRAFT">Draft</option>
                <option value="SUBMITTED">Submitted</option>
                <option value="APPROVED">Approved</option>
                <option value="PARTIALLY_RECEIVED">Partially received</option>
                <option value="FULLY_RECEIVED">Fully received</option>
                <option value="CANCELLED">Cancelled</option>
              </Select>
              <Input
                placeholder="Search number, supplier…"
                aria-label="Search purchase orders"
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
        <ErrorBanner error={ordersQuery.error} />
        {ordersQuery.isLoading ? (
          <Spinner />
        ) : !ordersQuery.data || ordersQuery.data.results.length === 0 ? (
          <EmptyState message="No purchase orders yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {ordersQuery.data.results.map((order) => (
              <li key={order.id} className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">
                      {order.number ?? `Draft ${order.id.slice(0, 8)}`}{" "}
                      {order.fulfilled_by_number ? (
                        <Link
                          href={`/purchases/${order.fulfilled_by}`}
                          className="text-xs text-slate-500 hover:underline"
                        >
                          → GRN {order.fulfilled_by_number}
                        </Link>
                      ) : null}
                    </p>
                    <p className="text-xs text-slate-500">
                      {order.supplier_name} · {formatDate(order.business_date)} ·{" "}
                      {order.items.length} line(s)
                      {order.expected_delivery_date
                        ? ` · expected ${formatDate(order.expected_delivery_date)}`
                        : null}
                    </p>
                  </div>
                  <Badge tone={poTone(order.status)}>{order.status}</Badge>
                </div>
                <p className="text-sm">
                  Total <strong>{formatMoney(order.grand_total)}</strong>
                  {order.status === "PARTIALLY_RECEIVED" || order.status === "FULLY_RECEIVED" ? (
                    <span className="text-xs text-slate-500">
                      {" "}
                      · received{" "}
                      {formatQty(
                        order.items.reduce((sum, item) => sum + Number(item.qty_received), 0),
                      )}{" "}
                      of{" "}
                      {formatQty(
                        order.items.reduce((sum, item) => sum + Number(item.qty_ordered), 0),
                      )}
                    </span>
                  ) : null}
                </p>
                <div className="flex flex-wrap gap-2">
                  {order.status === "DRAFT" && hasPerm("PURCHASE_MANAGE") ? (
                    <Button
                      size="sm"
                      onClick={() => submitMutation.mutate(order.id)}
                      disabled={submitMutation.isPending}
                    >
                      Submit
                    </Button>
                  ) : null}
                  {order.status === "SUBMITTED" && hasPerm("PURCHASE_CONFIRM") ? (
                    <Button
                      size="sm"
                      onClick={() => approveMutation.mutate(order.id)}
                      disabled={approveMutation.isPending}
                    >
                      Approve
                    </Button>
                  ) : null}
                  {(order.status === "APPROVED" || order.status === "PARTIALLY_RECEIVED") &&
                  hasPerm("PURCHASE_CONFIRM") ? (
                    <Button size="sm" variant="secondary" onClick={() => openConvert(order)}>
                      Receive
                    </Button>
                  ) : null}
                  {(order.status === "DRAFT" || order.status === "SUBMITTED") &&
                  hasPerm("PURCHASE_CONFIRM") ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setCancelFor(order);
                        setCancelReason("");
                      }}
                    >
                      Cancel
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
        {ordersQuery.data && ordersQuery.data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(ordersQuery.data.previous)}
            hasNext={Boolean(ordersQuery.data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
