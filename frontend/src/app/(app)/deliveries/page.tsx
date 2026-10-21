"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import type {
  Branch,
  Customer,
  DeliveryChallan,
  Medicine,
  Paginated,
  SalesInvoice,
} from "@/lib/types";

type DraftRow = {
  key: number;
  medicine: string;
  qty: string;
};

const newRow = (key: number): DraftRow => ({ key, medicine: "", qty: "" });

const emptyForm = {
  customer: "",
  branch: "",
  business_date: "",
  delivery_person: "",
  delivery_phone: "",
  vehicle_no: "",
  notes: "",
};

const STATUS_TONES: Record<
  DeliveryChallan["status"],
  "slate" | "blue" | "green" | "amber" | "rose"
> = {
  PREPARED: "slate",
  DISPATCHED: "blue",
  DELIVERED: "green",
  UNDELIVERED: "amber",
  CANCELLED: "rose",
};

export default function DeliveriesPage() {
  const { user, hasPerm } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(search);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyForm, branch: user?.default_branch_id ?? "" });
  const [rows, setRows] = useState<DraftRow[]>([newRow(1)]);
  const [rowSeq, setRowSeq] = useState(2);

  const [fromInvoiceFor, setFromInvoiceFor] = useState(false);
  const [invoiceId, setInvoiceId] = useState("");

  const [dispatchFor, setDispatchFor] = useState<DeliveryChallan | null>(null);
  const [deliverFor, setDeliverFor] = useState<DeliveryChallan | null>(null);
  const [recipientName, setRecipientName] = useState("");
  const [recipientPhone, setRecipientPhone] = useState("");
  const [cancelFor, setCancelFor] = useState<DeliveryChallan | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  const params = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) params.set("search", debouncedSearch);
  if (statusFilter) params.set("status", statusFilter);

  const challansQuery = useQuery({
    queryKey: ["delivery-challans", debouncedSearch, statusFilter, page],
    queryFn: () => api.get<Paginated<DeliveryChallan>>(`/delivery-challans/?${params.toString()}`),
  });
  const customersQuery = useQuery({
    queryKey: ["customers", "select"],
    queryFn: () => api.get<Paginated<Customer>>("/customers/?page_size=200&is_active=true"),
  });
  const medicinesQuery = useQuery({
    queryKey: ["medicines", "select"],
    queryFn: () => api.get<Paginated<Medicine>>("/medicines/?page_size=200&is_active=true"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });
  const pendingInvoicesQuery = useQuery({
    queryKey: ["sales", "pending-delivery"],
    queryFn: () => api.get<Paginated<SalesInvoice>>("/sales/?lifecycle=CONFIRMED&page_size=200"),
    enabled: fromInvoiceFor,
  });

  const pendingInvoices = (pendingInvoicesQuery.data?.results ?? []).filter(
    (invoice) => invoice.fulfillment_status === "PENDING",
  );

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["delivery-challans"] });
    queryClient.invalidateQueries({ queryKey: ["sales"] });
    queryClient.invalidateQueries({ queryKey: ["batches"] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
  };

  const createMutation = useMutation({
    meta: { successMessage: "Delivery challan created" },
    mutationFn: () =>
      api.postWithKey<DeliveryChallan>(
        "/delivery-challans/",
        {
          ...form,
          business_date: form.business_date || undefined,
          items: rows.map((row) => ({ medicine: row.medicine, qty: row.qty })),
        },
        `dc-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      ),
    onSuccess: () => {
      setForm({ ...emptyForm, branch: user?.default_branch_id ?? "" });
      setRows([newRow(1)]);
      setShowForm(false);
      invalidateAll();
    },
  });

  const fromInvoiceMutation = useMutation({
    meta: { successMessage: "Challan created from invoice" },
    mutationFn: () =>
      api.postWithKey<DeliveryChallan>(
        "/delivery-challans/from-invoice/",
        {
          invoice: invoiceId,
          delivery_person: form.delivery_person,
          delivery_phone: form.delivery_phone,
          vehicle_no: form.vehicle_no,
          notes: form.notes,
        },
        `dc-from-inv-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      ),
    onSuccess: () => {
      setFromInvoiceFor(false);
      setInvoiceId("");
      setForm({ ...emptyForm, branch: user?.default_branch_id ?? "" });
      invalidateAll();
    },
  });

  const dispatchMutation = useMutation({
    meta: { successMessage: "Challan dispatched" },
    mutationFn: (id: string) => api.post<DeliveryChallan>(`/delivery-challans/${id}/dispatch/`, {}),
    onSuccess: () => {
      setDispatchFor(null);
      invalidateAll();
    },
  });

  const deliverMutation = useMutation({
    meta: { successMessage: "Delivery marked as delivered" },
    mutationFn: () =>
      api.post<DeliveryChallan>(`/delivery-challans/${deliverFor?.id}/deliver/`, {
        recipient_name: recipientName,
        recipient_phone: recipientPhone,
      }),
    onSuccess: () => {
      setDeliverFor(null);
      setRecipientName("");
      setRecipientPhone("");
      invalidateAll();
    },
  });

  const undeliverMutation = useMutation({
    meta: { successMessage: "Challan marked undelivered" },
    mutationFn: (id: string) =>
      api.post<DeliveryChallan>(`/delivery-challans/${id}/undeliver/`, {}),
    onSuccess: invalidateAll,
  });

  const cancelMutation = useMutation({
    meta: { successMessage: "Challan cancelled" },
    mutationFn: () =>
      api.post(`/delivery-challans/${cancelFor?.id}/cancel/`, {
        reason: cancelReason || "Cancelled from delivery register",
      }),
    onSuccess: () => {
      setCancelFor(null);
      setCancelReason("");
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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Deliveries</h1>
        {hasPerm("SALE_CONFIRM") ? (
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => setFromInvoiceFor((v) => !v)}>
              {fromInvoiceFor ? "Close" : "New from invoice"}
            </Button>
            <Button size="sm" onClick={() => setShowForm((v) => !v)}>
              {showForm ? "Close" : "New challan"}
            </Button>
          </div>
        ) : null}
      </div>

      {/* Challan from invoice panel */}
      {fromInvoiceFor ? (
        <Card>
          <CardHeader
            title="New challan from invoice"
            subtitle="Pick a pending-delivery invoice; items and quantities are copied from it."
          />
          <form
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              fromInvoiceMutation.mutate();
            }}
            className="space-y-3 p-4"
          >
            <ErrorBanner error={fromInvoiceMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <div className="col-span-2">
                <Field label="Invoice">
                  <Select value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)} required>
                    <option value="">Select…</option>
                    {pendingInvoices.map((invoice) => (
                      <option key={invoice.id} value={invoice.id}>
                        {invoice.number} · {invoice.customer_name} ·{" "}
                        {formatMoney(invoice.grand_total)}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <Field label="Delivery person">
                <Input
                  value={form.delivery_person}
                  onChange={(e) => setForm({ ...form, delivery_person: e.target.value })}
                />
              </Field>
              <Field label="Delivery phone">
                <Input
                  value={form.delivery_phone}
                  onChange={(e) => setForm({ ...form, delivery_phone: e.target.value })}
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Field label="Vehicle #">
                <Input
                  value={form.vehicle_no}
                  onChange={(e) => setForm({ ...form, vehicle_no: e.target.value })}
                />
              </Field>
              <div className="col-span-2">
                <Field label="Notes">
                  <Input
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  />
                </Field>
              </div>
            </div>
            <Button
              type="submit"
              className="w-full lg:w-auto"
              disabled={fromInvoiceMutation.isPending || !invoiceId}
            >
              {fromInvoiceMutation.isPending ? "Creating…" : "Create challan"}
            </Button>
          </form>
        </Card>
      ) : null}

      {/* Manual challan form */}
      {showForm ? (
        <Card>
          <CardHeader
            title="New delivery challan"
            subtitle="Manual entry for non-invoice deliveries."
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
              <Field label="Customer" error={fieldError("customer")}>
                <Select
                  value={form.customer}
                  onChange={(e) => setForm({ ...form, customer: e.target.value })}
                  required
                >
                  <option value="">Select…</option>
                  {customersQuery.data?.results.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.name} ({customer.code})
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
              <Field label="Delivery person">
                <Input
                  value={form.delivery_person}
                  onChange={(e) => setForm({ ...form, delivery_person: e.target.value })}
                />
              </Field>
            </div>

            <div className="space-y-2">
              {rows.map((row, index) => (
                <div
                  key={row.key}
                  className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 p-3 lg:grid-cols-4"
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
                  <Field label="Qty">
                    <Input
                      type="number"
                      step="0.001"
                      min="0.001"
                      value={row.qty}
                      onChange={(e) => updateRow(row.key, { qty: e.target.value })}
                      required
                    />
                  </Field>
                  <div className="flex items-end">
                    {rows.length > 1 ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          setRows((prev) => prev.filter((item) => item.key !== row.key))
                        }
                      >
                        Remove
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

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              <Field label="Delivery phone">
                <Input
                  value={form.delivery_phone}
                  onChange={(e) => setForm({ ...form, delivery_phone: e.target.value })}
                />
              </Field>
              <Field label="Vehicle #">
                <Input
                  value={form.vehicle_no}
                  onChange={(e) => setForm({ ...form, vehicle_no: e.target.value })}
                />
              </Field>
              <Field label="Notes">
                <Input
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
              </Field>
            </div>

            <Button type="submit" className="w-full lg:w-auto" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Create challan"}
            </Button>
          </form>
        </Card>
      ) : null}

      {/* Dispatch confirm panel */}
      {dispatchFor ? (
        <Card>
          <CardHeader
            title={`Dispatch ${dispatchFor.number}`}
            subtitle={`${dispatchFor.customer_name} · ${dispatchFor.items.length} line(s)`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setDispatchFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={dispatchMutation.error} />
            <p className="text-sm text-slate-600">Mark this challan as out for delivery?</p>
            <Button
              onClick={() => dispatchMutation.mutate(dispatchFor.id)}
              disabled={dispatchMutation.isPending}
            >
              {dispatchMutation.isPending ? "Dispatching…" : "Dispatch"}
            </Button>
          </div>
        </Card>
      ) : null}

      {/* Deliver panel */}
      {deliverFor ? (
        <Card>
          <CardHeader
            title={`Deliver ${deliverFor.number}`}
            subtitle={`${deliverFor.customer_name} · record proof-of-delivery recipient`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setDeliverFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={deliverMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              <Field label="Recipient name">
                <Input value={recipientName} onChange={(e) => setRecipientName(e.target.value)} />
              </Field>
              <Field label="Recipient phone">
                <Input value={recipientPhone} onChange={(e) => setRecipientPhone(e.target.value)} />
              </Field>
            </div>
            <Button onClick={() => deliverMutation.mutate()} disabled={deliverMutation.isPending}>
              {deliverMutation.isPending ? "Marking…" : "Mark delivered"}
            </Button>
          </div>
        </Card>
      ) : null}

      {cancelFor ? (
        <Card>
          <CardHeader
            title={`Cancel challan ${cancelFor.number ?? ""}`}
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
              {cancelMutation.isPending ? "Cancelling…" : "Cancel challan"}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Delivery register"
          subtitle={challansQuery.data ? `${challansQuery.data.count} challan(s)` : undefined}
          action={
            <div className="flex flex-wrap gap-2">
              <Select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="w-44"
                aria-label="Filter by status"
              >
                <option value="">All statuses</option>
                <option value="PREPARED">Prepared</option>
                <option value="DISPATCHED">Dispatched</option>
                <option value="DELIVERED">Delivered</option>
                <option value="UNDELIVERED">Undelivered</option>
                <option value="CANCELLED">Cancelled</option>
              </Select>
              <Input
                placeholder="Search number, customer, vehicle…"
                aria-label="Search challans"
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
        <ErrorBanner error={challansQuery.error} />
        {challansQuery.isLoading ? (
          <Spinner />
        ) : !challansQuery.data || challansQuery.data.results.length === 0 ? (
          <EmptyState message="No delivery challans yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {challansQuery.data.results.map((challan) => (
              <li key={challan.id} className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">
                      {challan.number ?? `Draft ${challan.id.slice(0, 8)}`}{" "}
                      {challan.invoice_number ? (
                        <span className="text-xs text-slate-500">
                          · INV {challan.invoice_number}
                        </span>
                      ) : null}
                    </p>
                    <p className="text-xs text-slate-500">
                      {challan.customer_name} ({challan.customer_code}) ·{" "}
                      {formatDate(challan.business_date)} · {challan.items.length} line(s) ·{" "}
                      {formatQty(challan.items.reduce((sum, item) => sum + Number(item.qty), 0))}{" "}
                      pcs
                    </p>
                    {challan.delivery_person ? (
                      <p className="text-xs text-slate-500">
                        {challan.delivery_person}
                        {challan.delivery_phone ? ` · ${challan.delivery_phone}` : null}
                        {challan.vehicle_no ? ` · vehicle ${challan.vehicle_no}` : null}
                      </p>
                    ) : null}
                  </div>
                  <Badge tone={STATUS_TONES[challan.status]}>{challan.status}</Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  {challan.status === "PREPARED" && hasPerm("SALE_CONFIRM") ? (
                    <Button
                      size="sm"
                      onClick={() => setDispatchFor(challan)}
                      disabled={dispatchMutation.isPending}
                    >
                      Dispatch
                    </Button>
                  ) : null}
                  {challan.status === "DISPATCHED" && hasPerm("SALE_CONFIRM") ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setDeliverFor(challan);
                        setRecipientName("");
                        setRecipientPhone("");
                      }}
                    >
                      Mark delivered
                    </Button>
                  ) : null}
                  {challan.status === "DELIVERED" && hasPerm("SALE_CONFIRM") ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => undeliverMutation.mutate(challan.id)}
                      disabled={undeliverMutation.isPending}
                    >
                      Undeliver
                    </Button>
                  ) : null}
                  {(challan.status === "PREPARED" || challan.status === "DISPATCHED") &&
                  hasPerm("SALE_CONFIRM") ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setCancelFor(challan);
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
        {challansQuery.data && challansQuery.data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(challansQuery.data.previous)}
            hasNext={Boolean(challansQuery.data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
