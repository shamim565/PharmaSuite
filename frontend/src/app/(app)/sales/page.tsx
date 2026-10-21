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
  ConfirmButton,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Pagination,
  Select,
  Spinner,
} from "@/components/ui";
import { ApiError, api, apiDownload, newIdempotencyKey } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type {
  Branch,
  Customer,
  Doctor,
  FinancialAccount,
  Medicine,
  MedicineBatch,
  Paginated,
  Representative,
  SalesInvoice,
} from "@/lib/types";

type DraftRow = {
  key: number;
  medicine: string;
  qty: string;
  unit_price: string;
  line_discount: string;
  vat_rate: string;
  is_free_goods: boolean;
  batch: string;
};

const newRow = (key: number): DraftRow => ({
  key,
  medicine: "",
  qty: "",
  unit_price: "",
  line_discount: "0",
  vat_rate: "",
  is_free_goods: false,
  batch: "",
});

const emptyForm = {
  customer: "",
  branch: "",
  business_date: "",
  notes: "",
  doctor: "",
  sales_rep: "",
  fefo_override_reason: "",
};

function BatchSelect({
  branch,
  medicine,
  value,
  onChange,
}: {
  branch: string;
  medicine: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const { data } = useQuery({
    queryKey: ["batches", "sale-override", branch, medicine],
    queryFn: () =>
      api.get<Paginated<MedicineBatch>>(
        `/batches/?page_size=100&branch=${branch}&medicine=${medicine}`,
      ),
    enabled: Boolean(branch && medicine),
  });
  return (
    <Field label="Batch (FEFO override)">
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">FEFO (auto)</option>
        {data?.results.map((batch) => (
          <option key={batch.id} value={batch.id}>
            {batch.batch_number} · {batch.expiry_date ?? "no expiry"} · qty {batch.qty_on_hand}
          </option>
        ))}
      </Select>
    </Field>
  );
}

function tierPrice(customer: Customer, medicine: Medicine): number {
  if (customer.price_tier === "WHOLESALE" && medicine.wholesale_price) {
    return Number(medicine.wholesale_price);
  }
  if (customer.price_tier === "CUSTOM" && medicine.custom_price) {
    return Number(medicine.custom_price);
  }
  if (customer.price_tier === "RETAIL" && medicine.retail_price) {
    return Number(medicine.retail_price);
  }
  return Number(medicine.selling_price);
}

function lifecycleTone(status: SalesInvoice["lifecycle"]): "green" | "slate" | "rose" {
  return status === "CONFIRMED" ? "green" : status === "CANCELLED" ? "rose" : "slate";
}

function paymentTone(status: SalesInvoice["payment_status"]): "green" | "amber" | "slate" {
  return status === "PAID" ? "green" : status === "PARTIALLY_PAID" ? "amber" : "slate";
}

export default function SalesPage() {
  const queryClient = useQueryClient();
  const { hasPerm, user } = useAuth();
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [rows, setRows] = useState<DraftRow[]>([newRow(1)]);
  const [rowSeq, setRowSeq] = useState(2);

  const [confirmFor, setConfirmFor] = useState<SalesInvoice | null>(null);
  const [payFor, setPayFor] = useState<SalesInvoice | null>(null);
  const [payAmount, setPayAmount] = useState("");
  const [payAccount, setPayAccount] = useState("");
  const [payMethod, setPayMethod] = useState("CASH");
  const [payReference, setPayReference] = useState("");
  const [creditOverride, setCreditOverride] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [rxNumber, setRxNumber] = useState("");
  const [rxOverride, setRxOverride] = useState(false);
  const [rxOverrideReason, setRxOverrideReason] = useState("");
  const [returnFor, setReturnFor] = useState<SalesInvoice | null>(null);
  const [returnItemId, setReturnItemId] = useState("");
  const [returnQty, setReturnQty] = useState("");
  const [returnCondition, setReturnCondition] = useState("RESELLABLE");
  const [returnReason, setReturnReason] = useState("CUSTOMER_RETURN");
  const [returnRefundMethod, setReturnRefundMethod] = useState("CUSTOMER_CREDIT");
  const [returnAccountId, setReturnAccountId] = useState("");
  const [cancelFor, setCancelFor] = useState<SalesInvoice | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [confirmKey, setConfirmKey] = useState(newIdempotencyKey());
  const [payKey, setPayKey] = useState(newIdempotencyKey());
  const [returnKey, setReturnKey] = useState(newIdempotencyKey());
  const [cancelKey, setCancelKey] = useState(newIdempotencyKey());

  const debouncedSearch = useDebouncedValue(search);

  const salesParams = new URLSearchParams({ page_size: "25", page: String(page) });
  if (debouncedSearch) salesParams.set("search", debouncedSearch);
  if (dateFrom) salesParams.set("date_from", dateFrom);
  if (dateTo) salesParams.set("date_to", dateTo);

  const salesQuery = useQuery({
    queryKey: ["sales", debouncedSearch, dateFrom, dateTo, page],
    queryFn: () => api.get<Paginated<SalesInvoice>>(`/sales/?${salesParams.toString()}`),
  });
  const customersQuery = useQuery({
    queryKey: ["customers", "select"],
    queryFn: () => api.get<Paginated<Customer>>("/customers/?page_size=200&is_active=true"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });
  const medicinesQuery = useQuery({
    queryKey: ["medicines", "select"],
    queryFn: () => api.get<Paginated<Medicine>>("/medicines/?page_size=200&is_active=true"),
  });
  const selectedMedicine = rows.find((row) => row.medicine)?.medicine;
  const availabilityQuery = useQuery({
    queryKey: ["fefo-availability", user?.default_branch_id, selectedMedicine],
    queryFn: () =>
      api.get<{
        results: Array<{
          batch_number: string;
          expiry_date: string | null;
          qty_on_hand: string;
          days_to_expiry: number | null;
        }>;
      }>(`/sales/fefo/?branch=${user?.default_branch_id}&medicine=${selectedMedicine}`),
    enabled: Boolean(selectedMedicine) && Boolean(user?.default_branch_id),
  });
  const availability = availabilityQuery.data?.results ?? [];
  const availableQty = availability.reduce((sum, row) => sum + Number(row.qty_on_hand), 0);
  const nearestExpiry = availability.length
    ? availability.reduce((a, b) => ((a.expiry_date ?? "9999") < (b.expiry_date ?? "9999") ? a : b))
        .expiry_date
    : null;
  const accountsQuery = useQuery({
    queryKey: ["accounts", "select"],
    queryFn: () => api.get<Paginated<FinancialAccount>>("/accounts/?page_size=50&is_active=true"),
  });
  const doctorsQuery = useQuery({
    queryKey: ["doctors", "select"],
    queryFn: () => api.get<Paginated<Doctor>>("/doctors/?page_size=200&is_active=true"),
  });
  const repsQuery = useQuery({
    queryKey: ["reps", "select"],
    queryFn: () =>
      api.get<Paginated<Representative>>("/representatives/?page_size=100&is_active=true"),
  });
  const configQuery = useQuery({
    queryKey: ["sales-config"],
    queryFn: () => api.get<{ vat_enabled: boolean }>("/sales/config/"),
  });
  const vatEnabled = configQuery.data?.vat_enabled ?? false;

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["sales"] });
    queryClient.invalidateQueries({ queryKey: ["sales-returns"] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["customers"] });
    queryClient.invalidateQueries({ queryKey: ["batches"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const createMutation = useMutation({
    meta: { successMessage: "Invoice saved as draft" },
    mutationFn: () =>
      api.post<SalesInvoice>("/sales/", {
        ...form,
        business_date: form.business_date || undefined,
        doctor: form.doctor || null,
        sales_rep: form.sales_rep || null,
        items: rows.map((row) => ({
          medicine: row.medicine,
          qty: row.qty,
          unit_price: row.unit_price || null,
          line_discount: row.line_discount === "" ? null : row.line_discount,
          vat_rate: row.is_free_goods || row.vat_rate === "" ? null : row.vat_rate,
          is_free_goods: row.is_free_goods,
          batch: row.batch || null,
          fefo_override_reason: row.batch ? form.fefo_override_reason : "",
        })),
      }),
    onSuccess: () => {
      setForm(emptyForm);
      setRows([newRow(1)]);
      setShowForm(false);
      invalidateAll();
    },
  });

  const confirmMutation = useMutation({
    meta: { successMessage: "Invoice confirmed" },
    mutationFn: () =>
      api.postWithKey<SalesInvoice>(
        `/sales/${confirmFor?.id}/confirm/`,
        {
          payment:
            Number(payAmount) > 0
              ? {
                  amount: payAmount,
                  method: payMethod,
                  account: payAccount,
                  reference: payReference,
                }
              : null,
          allow_credit_override: creditOverride,
          credit_override_reason: overrideReason,
          prescription_number: rxNumber,
          rx_override: rxOverride,
          rx_override_reason: rxOverrideReason,
        },
        confirmKey,
      ),
    onSuccess: () => {
      setConfirmFor(null);
      setPayAmount("");
      setPayReference("");
      setCreditOverride(false);
      setOverrideReason("");
      setRxNumber("");
      setRxOverride(false);
      setRxOverrideReason("");
      setConfirmKey(newIdempotencyKey());
      invalidateAll();
    },
  });

  const payMutation = useMutation({
    meta: { successMessage: "Payment posted" },
    mutationFn: () =>
      api.postWithKey(
        "/payments/",
        {
          customer: payFor?.customer,
          branch: payFor?.branch,
          amount: payAmount,
          method: payMethod,
          account: payAccount,
          reference: payReference,
          allocations: [{ invoice: payFor?.id, amount: payAmount }],
        },
        payKey,
      ),
    onSuccess: () => {
      setPayFor(null);
      setPayAmount("");
      setPayReference("");
      setPayKey(newIdempotencyKey());
      invalidateAll();
    },
  });

  const cancelMutation = useMutation({
    meta: { successMessage: "Invoice cancelled" },
    mutationFn: () =>
      api.postWithKey(
        `/sales/${cancelFor?.id}/cancel/`,
        { reason: cancelReason || "Cancelled from sales register" },
        cancelKey,
      ),
    onSuccess: () => {
      setCancelFor(null);
      setCancelReason("");
      setCancelKey(newIdempotencyKey());
      invalidateAll();
    },
  });

  const deliveredMutation = useMutation({
    meta: { successMessage: "Marked as delivered" },
    mutationFn: (invoice: SalesInvoice) => api.post(`/sales/${invoice.id}/mark-delivered/`, {}),
    onSuccess: () => invalidateAll(),
  });

  const deleteDraftMutation = useMutation({
    meta: { successMessage: "Draft deleted" },
    mutationFn: (invoice: SalesInvoice) => api.delete(`/sales/${invoice.id}/`),
    onSuccess: () => invalidateAll(),
  });

  const returnMutation = useMutation({
    meta: { successMessage: "Return created and confirmed" },
    mutationFn: async () => {
      const draft = await api.postWithKey<{ id: string }>(
        "/sales-returns/",
        {
          invoice: returnFor?.id,
          reason_code: returnReason,
          refund_method: returnRefundMethod,
          refund_account:
            returnRefundMethod === "CASH" || returnRefundMethod === "BANK" ? returnAccountId : null,
          items: [{ invoice_item: returnItemId, qty: returnQty, condition: returnCondition }],
        },
        returnKey,
      );
      return api.post(`/sales-returns/${draft.id}/confirm/`, {});
    },
    onSuccess: () => {
      setReturnFor(null);
      setReturnItemId("");
      setReturnQty("");
      setReturnKey(newIdempotencyKey());
      invalidateAll();
    },
  });

  const openReturn = (invoice: SalesInvoice) => {
    const firstReturnable = invoice.items.find((item) => Number(item.qty) > 0);
    setReturnFor(invoice);
    setReturnItemId(firstReturnable?.id ?? "");
    setReturnQty("");
    setReturnCondition("RESELLABLE");
    setReturnReason("CUSTOMER_RETURN");
    setReturnRefundMethod("CUSTOMER_CREDIT");
    setReturnAccountId(accountsQuery.data?.results[0]?.id ?? "");
    setReturnKey(newIdempotencyKey());
  };

  const selectedReturnItem = returnFor?.items.find((item) => item.id === returnItemId);

  const openConfirm = (invoice: SalesInvoice) => {
    setConfirmFor(invoice);
    setPayAmount("");
    setPayMethod("CASH");
    setPayAccount(accountsQuery.data?.results[0]?.id ?? "");
    setCreditOverride(false);
    setOverrideReason("");
    setRxNumber("");
    setRxOverride(false);
    setRxOverrideReason("");
    setConfirmKey(newIdempotencyKey());
  };

  const openPay = (invoice: SalesInvoice) => {
    setPayFor(invoice);
    setPayAmount(invoice.outstanding);
    setPayMethod("CASH");
    setPayAccount(accountsQuery.data?.results[0]?.id ?? "");
    setPayKey(newIdempotencyKey());
  };

  const openCancel = (invoice: SalesInvoice) => {
    setCancelFor(invoice);
    setCancelReason("");
    setCancelKey(newIdempotencyKey());
  };

  const updateRow = (key: number, patch: Partial<DraftRow>) => {
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  };

  const addRow = () => {
    setRows((prev) => [...prev, newRow(rowSeq)]);
    setRowSeq((value) => value + 1);
  };

  const [scanValue, setScanValue] = useState("");

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  const confirmError = confirmMutation.error;
  const creditBlocked =
    confirmError instanceof ApiError &&
    (confirmError.code === "CREDIT_LIMIT_EXCEEDED" || confirmError.code === "CUSTOMER_PAST_DUE");

  const preview = rows.reduce(
    (totals, row) => {
      const qty = Number(row.qty || 0);
      if (!row.medicine || qty <= 0) return totals;
      const medicine = medicinesQuery.data?.results.find((item) => item.id === row.medicine);
      const customer = customersQuery.data?.results.find((item) => item.id === form.customer);
      const unitPrice = row.is_free_goods
        ? 0
        : row.unit_price === ""
          ? medicine && customer
            ? tierPrice(customer, medicine)
            : 0
          : Number(row.unit_price);
      const gross = qty * unitPrice;
      let discount = row.line_discount === "" ? 0 : Number(row.line_discount);
      if (row.line_discount === "" && !row.is_free_goods && customer) {
        discount = (gross * Number(customer.default_discount_pct)) / 100;
      }
      const taxable = gross - discount;
      const rate =
        vatEnabled && medicine && !row.is_free_goods
          ? Number(row.vat_rate || medicine.vat_rate)
          : 0;
      totals.subtotal += gross;
      totals.discount += discount;
      totals.vat += (taxable * rate) / 100;
      return totals;
    },
    { subtotal: 0, discount: 0, vat: 0 },
  );
  const previewGrand = Math.round(preview.subtotal - preview.discount + preview.vat);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Sales</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "New invoice"}
        </Button>
      </div>

      {showForm ? (
        <Card>
          <CardHeader title="New invoice" subtitle="Stock is deducted FEFO at confirmation." />
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
                      {customer.name} ({formatMoney(customer.balance_cache)})
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
                />
              </Field>
              <Field label="Doctor (optional attribution)">
                <Select
                  value={form.doctor}
                  onChange={(e) => setForm({ ...form, doctor: e.target.value })}
                >
                  <option value="">—</option>
                  {doctorsQuery.data?.results.map((doctor) => (
                    <option key={doctor.id} value={doctor.id}>
                      {doctor.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Sales rep (optional)">
                <Select
                  value={form.sales_rep}
                  onChange={(e) => setForm({ ...form, sales_rep: e.target.value })}
                >
                  <option value="">—</option>
                  {repsQuery.data?.results.map((rep) => (
                    <option key={rep.id} value={rep.id}>
                      {rep.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            {hasPerm("INV_OVERRIDE_FEFO") && rows.some((row) => row.batch) ? (
              <Field label="FEFO override reason (required when a batch is selected)">
                <Input
                  value={form.fefo_override_reason}
                  onChange={(e) => setForm({ ...form, fefo_override_reason: e.target.value })}
                  placeholder="e.g. customer requested later expiry"
                />
              </Field>
            ) : null}

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Input
                  value={scanValue}
                  onChange={(e) => setScanValue(e.target.value)}
                  onKeyDown={async (e) => {
                    if (e.key !== "Enter") return;
                    const value = scanValue.trim();
                    if (!value) return;
                    e.preventDefault();
                    try {
                      const response = await api.get<Paginated<Medicine>>(
                        `/medicines/?page_size=1&search=${encodeURIComponent(value)}`,
                      );
                      const match = response.results[0];
                      if (match) {
                        addRow();
                        setRows((prev) => {
                          const next = [...prev];
                          next[next.length - 1] = { ...next[next.length - 1], medicine: match.id };
                          return next;
                        });
                        setScanValue("");
                      }
                    } catch {
                      // ignore scan misses
                    }
                  }}
                  placeholder="Scan or type barcode / medicine code, then Enter"
                />
              </div>
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
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && index === rows.length - 1) {
                            e.preventDefault();
                            addRow();
                          }
                        }}
                        required
                      >
                        <option value="">Select…</option>
                        {medicinesQuery.data?.results.map((medicine) => (
                          <option key={medicine.id} value={medicine.id}>
                            {medicine.name} ({medicine.code})
                            {medicine.pack_size && Number(medicine.pack_size) > 1
                              ? ` · pack of ${medicine.pack_size}`
                              : ""}
                          </option>
                        ))}
                      </Select>
                      {(() => {
                        const selected = medicinesQuery.data?.results.find(
                          (m) => m.id === row.medicine,
                        );
                        const packSize = selected ? Number(selected.pack_size) : 0;
                        if (!selected || packSize <= 1) return null;
                        return (
                          <Input
                            className="mt-1"
                            type="number"
                            min="1"
                            placeholder={`Whole packs (each = ${packSize} units)`}
                            onChange={(e) => {
                              const packs = Number(e.target.value);
                              if (packs > 0) updateRow(row.key, { qty: String(packs * packSize) });
                            }}
                          />
                        );
                      })()}
                      {row.medicine === selectedMedicine && availability.length > 0 ? (
                        <p className="mt-1 text-xs text-slate-500">
                          Available {formatQty(availableQty)}
                          {nearestExpiry ? ` · nearest expiry ${formatDate(nearestExpiry)}` : ""}
                        </p>
                      ) : null}
                    </Field>
                  </div>
                  <Field label="Qty">
                    <Input
                      type="number"
                      step="0.001"
                      min="0.001"
                      value={row.qty}
                      onChange={(e) => updateRow(row.key, { qty: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && index === rows.length - 1) {
                          e.preventDefault();
                          addRow();
                        }
                      }}
                      required
                    />
                  </Field>
                  <Field label="Unit price (auto if blank)">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={row.unit_price}
                      onChange={(e) => updateRow(row.key, { unit_price: e.target.value })}
                      disabled={row.is_free_goods}
                    />
                  </Field>
                  <Field label="Discount">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={row.line_discount}
                      onChange={(e) => updateRow(row.key, { line_discount: e.target.value })}
                      disabled={row.is_free_goods}
                    />
                  </Field>
                  <Field label="VAT %">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={row.vat_rate}
                      onChange={(e) => updateRow(row.key, { vat_rate: e.target.value })}
                      disabled={!vatEnabled || row.is_free_goods}
                      placeholder={
                        medicinesQuery.data?.results.find((item) => item.id === row.medicine)
                          ?.vat_rate ?? "—"
                      }
                    />
                  </Field>
                  <label className="flex items-end gap-2 pb-2 text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={row.is_free_goods}
                      onChange={(e) => updateRow(row.key, { is_free_goods: e.target.checked })}
                    />
                    Free goods
                  </label>
                  {hasPerm("INV_OVERRIDE_FEFO") && row.medicine && form.branch ? (
                    <div className="col-span-2 lg:col-span-3">
                      <BatchSelect
                        branch={form.branch}
                        medicine={row.medicine}
                        value={row.batch}
                        onChange={(value) => updateRow(row.key, { batch: value })}
                      />
                    </div>
                  ) : null}
                  {rows.length > 1 ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setRows((prev) => prev.filter((item) => item.key !== row.key))}
                    >
                      Remove
                    </Button>
                  ) : null}
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

            <div className="flex flex-wrap items-center justify-end gap-4 rounded-lg bg-slate-50 px-4 py-3 text-sm">
              <span className="text-slate-500">Subtotal {formatMoney(preview.subtotal)}</span>
              {preview.discount > 0 ? (
                <span className="text-slate-500">Discount −{formatMoney(preview.discount)}</span>
              ) : null}
              <span className="text-slate-500">
                VAT {vatEnabled ? formatMoney(preview.vat) : "0.00 (disabled)"}
              </span>
              <span className="font-semibold text-slate-800">
                Estimated total {formatMoney(previewGrand)}
              </span>
            </div>

            <Button type="submit" className="w-full lg:w-auto" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Save draft"}
            </Button>
          </form>
        </Card>
      ) : null}

      {confirmFor ? (
        <Card>
          <CardHeader
            title={`Confirm invoice — ${confirmFor.customer_name}`}
            subtitle={`Total ${formatMoney(confirmFor.grand_total)}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setConfirmFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={confirmMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Field label="Receive now (amount)">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                />
              </Field>
              <Field label="Method">
                <Select value={payMethod} onChange={(e) => setPayMethod(e.target.value)}>
                  <option value="CASH">Cash</option>
                  <option value="BANK">Bank</option>
                  <option value="MFS">MFS</option>
                  <option value="CHEQUE">Cheque</option>
                </Select>
              </Field>
              <Field label="Account">
                <Select value={payAccount} onChange={(e) => setPayAccount(e.target.value)}>
                  <option value="">Select…</option>
                  {accountsQuery.data?.results.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name} ({formatMoney(account.balance_cache)})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reference">
                <Input value={payReference} onChange={(e) => setPayReference(e.target.value)} />
              </Field>
            </div>
            {confirmFor && confirmFor.items.some((item) => item.medicine_rx_required) ? (
              <div className="space-y-2 rounded-lg border border-sky-200 bg-sky-50 p-3">
                <p className="text-xs font-semibold uppercase text-sky-800">
                  Rx medicines in this invoice
                </p>
                <p className="text-xs text-sky-700">
                  {confirmFor.items
                    .filter((item) => item.medicine_rx_required)
                    .map((item) => item.medicine_name)
                    .join(", ")}
                </p>
                <Field label="Prescription number">
                  <Input
                    value={rxNumber}
                    onChange={(e) => setRxNumber(e.target.value)}
                    placeholder="e.g. RX-2026-00123"
                  />
                </Field>
                <label className="flex items-center gap-2 text-sm text-sky-800">
                  <input
                    type="checkbox"
                    checked={rxOverride}
                    onChange={(e) => setRxOverride(e.target.checked)}
                  />
                  No prescription captured (override, audited)
                </label>
                {rxOverride ? (
                  <Input
                    placeholder="Override reason (required)"
                    value={rxOverrideReason}
                    onChange={(e) => setRxOverrideReason(e.target.value)}
                  />
                ) : null}
              </div>
            ) : null}
            {creditBlocked && hasPerm("SALE_OVERRIDE_CREDIT") ? (
              <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <label className="flex items-center gap-2 text-sm text-amber-800">
                  <input
                    type="checkbox"
                    checked={creditOverride}
                    onChange={(e) => setCreditOverride(e.target.checked)}
                  />
                  Override credit limit (audited)
                </label>
                <Input
                  placeholder="Override reason"
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                />
              </div>
            ) : null}
            <Button
              onClick={() => confirmMutation.mutate()}
              disabled={confirmMutation.isPending || (Number(payAmount) > 0 && !payAccount)}
            >
              {confirmMutation.isPending ? "Confirming…" : "Confirm invoice"}
            </Button>
          </div>
        </Card>
      ) : null}

      {payFor ? (
        <Card>
          <CardHeader
            title={`Receive payment — ${payFor.customer_name}`}
            subtitle={`Outstanding ${formatMoney(payFor.outstanding)} on ${payFor.number}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setPayFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={payMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Field label="Amount">
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                />
              </Field>
              <Field label="Method">
                <Select value={payMethod} onChange={(e) => setPayMethod(e.target.value)}>
                  <option value="CASH">Cash</option>
                  <option value="BANK">Bank</option>
                  <option value="MFS">MFS</option>
                  <option value="CHEQUE">Cheque</option>
                </Select>
              </Field>
              <Field label="Account">
                <Select value={payAccount} onChange={(e) => setPayAccount(e.target.value)}>
                  <option value="">Select…</option>
                  {accountsQuery.data?.results.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name} ({formatMoney(account.balance_cache)})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reference">
                <Input value={payReference} onChange={(e) => setPayReference(e.target.value)} />
              </Field>
            </div>
            <Button
              onClick={() => payMutation.mutate()}
              disabled={payMutation.isPending || !payAccount || !payAmount}
            >
              {payMutation.isPending ? "Posting…" : "Post receipt"}
            </Button>
          </div>
        </Card>
      ) : null}

      {returnFor ? (
        <Card>
          <CardHeader
            title={`Return against ${returnFor.number}`}
            subtitle={`${returnFor.customer_name} · resellable goods are restocked; damaged/expired go to quarantine.`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setReturnFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={returnMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <div className="col-span-2">
                <Field label="Invoice line">
                  <Select
                    value={returnItemId}
                    onChange={(e) => {
                      setReturnItemId(e.target.value);
                      setReturnQty("");
                    }}
                  >
                    <option value="">Select…</option>
                    {returnFor.items.map((item) => {
                      const returnable = Number(item.qty) - Number(item.returned_qty ?? 0);
                      return (
                        <option key={item.id} value={item.id} disabled={returnable <= 0}>
                          {item.medicine_name} · {item.batch_number} · returnable{" "}
                          {formatQty(returnable)}
                        </option>
                      );
                    })}
                  </Select>
                </Field>
              </div>
              <Field label="Quantity">
                <Input
                  type="number"
                  step="0.001"
                  min="0.001"
                  value={returnQty}
                  onChange={(e) => setReturnQty(e.target.value)}
                />
              </Field>
              <Field label="Condition">
                <Select
                  value={returnCondition}
                  onChange={(e) => setReturnCondition(e.target.value)}
                >
                  <option value="RESELLABLE">Resellable (restock)</option>
                  <option value="DAMAGED">Damaged (quarantine)</option>
                  <option value="EXPIRED">Expired (quarantine)</option>
                </Select>
              </Field>
              <Field label="Reason">
                <Select value={returnReason} onChange={(e) => setReturnReason(e.target.value)}>
                  <option value="CUSTOMER_RETURN">Customer return</option>
                  <option value="DAMAGED">Damaged</option>
                  <option value="EXPIRED_AT_CUSTOMER">Expired at customer</option>
                  <option value="WRONG_ITEM">Wrong item</option>
                  <option value="EXCESS_SUPPLY">Excess supply</option>
                </Select>
              </Field>
              <Field label="Refund method">
                <Select
                  value={returnRefundMethod}
                  onChange={(e) => setReturnRefundMethod(e.target.value)}
                >
                  <option value="CUSTOMER_CREDIT">Customer credit</option>
                  <option value="ADJUST_DUES">Adjust dues</option>
                  <option value="CASH">Cash refund</option>
                  <option value="BANK">Bank refund</option>
                </Select>
              </Field>
              {returnRefundMethod === "CASH" || returnRefundMethod === "BANK" ? (
                <Field label="Refund account">
                  <Select
                    value={returnAccountId}
                    onChange={(e) => setReturnAccountId(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {accountsQuery.data?.results.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name} ({formatMoney(account.balance_cache)})
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
            </div>
            {selectedReturnItem ? (
              <p className="text-xs text-slate-500">
                Returnable now:{" "}
                {formatQty(
                  Number(selectedReturnItem.qty) - Number(selectedReturnItem.returned_qty ?? 0),
                )}{" "}
                · unit price {formatMoney(selectedReturnItem.unit_price)}
              </p>
            ) : null}
            <Button
              onClick={() => returnMutation.mutate()}
              disabled={
                returnMutation.isPending ||
                !returnItemId ||
                !returnQty ||
                ((returnRefundMethod === "CASH" || returnRefundMethod === "BANK") &&
                  !returnAccountId)
              }
            >
              {returnMutation.isPending ? "Processing…" : "Create & confirm return"}
            </Button>
          </div>
        </Card>
      ) : null}

      {cancelFor ? (
        <Card>
          <CardHeader
            title={`Cancel invoice ${cancelFor.number ?? ""}`}
            subtitle="Allowed only when unpaid and unreturned; stock is restored."
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
              {cancelMutation.isPending ? "Cancelling…" : "Cancel invoice"}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Sales register"
          subtitle={salesQuery.data ? `${salesQuery.data.count} invoice(s)` : undefined}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPage(1);
                }}
                className="w-36"
              />
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPage(1);
                }}
                className="w-36"
              />
              <Input
                placeholder="Search number, customer…"
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
        <ErrorBanner error={salesQuery.error} />
        <ErrorBanner error={deleteDraftMutation.error} />
        {salesQuery.isLoading ? (
          <Spinner />
        ) : !salesQuery.data || salesQuery.data.results.length === 0 ? (
          <EmptyState message="No invoices yet." />
        ) : (
          <>
            <ul className="divide-y divide-slate-100">
              {salesQuery.data.results.map((invoice) => (
                <li key={invoice.id} className="space-y-2 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium">
                        <Link
                          href={`/sales/${invoice.id}`}
                          className="text-primary-700 hover:underline"
                        >
                          {invoice.number ?? "Draft"}
                        </Link>{" "}
                        <span className="text-xs text-slate-500">{invoice.customer_name}</span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatDate(invoice.business_date)} · {invoice.items.length} line(s)
                        {invoice.due_date ? ` · due ${formatDate(invoice.due_date)}` : ""}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={lifecycleTone(invoice.lifecycle)}>{invoice.lifecycle}</Badge>
                      <Badge tone={paymentTone(invoice.payment_status)}>
                        {invoice.payment_status}
                      </Badge>
                      {invoice.fulfillment_status === "DELIVERED" ? (
                        <Badge tone="blue">Delivered</Badge>
                      ) : null}
                      {invoice.credit_override ? <Badge tone="amber">Credit override</Badge> : null}
                      {invoice.fefo_override ? <Badge tone="amber">FEFO override</Badge> : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm">
                      Total <strong>{formatMoney(invoice.grand_total)}</strong> · Paid{" "}
                      {formatMoney(invoice.paid_total)} ·{" "}
                      <span
                        className={
                          Number(invoice.outstanding) > 0 ? "text-danger-700" : "text-primary-700"
                        }
                      >
                        Outstanding {formatMoney(invoice.outstanding)}
                      </span>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {invoice.lifecycle === "DRAFT" ? (
                        <>
                          <Button
                            size="sm"
                            onClick={() => openConfirm(invoice)}
                            disabled={!accountsQuery.data}
                          >
                            Confirm
                          </Button>
                          <ConfirmButton
                            size="sm"
                            variant="ghost"
                            confirmLabel="Delete draft?"
                            onConfirm={() => deleteDraftMutation.mutate(invoice)}
                            disabled={deleteDraftMutation.isPending}
                          >
                            Delete
                          </ConfirmButton>
                        </>
                      ) : null}
                      {invoice.lifecycle === "CONFIRMED" && Number(invoice.outstanding) > 0 ? (
                        <Button size="sm" variant="secondary" onClick={() => openPay(invoice)}>
                          Receive payment
                        </Button>
                      ) : null}
                      {invoice.lifecycle === "CONFIRMED" &&
                      Number(invoice.paid_total) === 0 &&
                      invoice.return_status === "NONE" &&
                      hasPerm("SALE_CANCEL") ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => openCancel(invoice)}
                          disabled={cancelMutation.isPending}
                        >
                          Cancel
                        </Button>
                      ) : null}
                      {invoice.lifecycle === "CONFIRMED" &&
                      invoice.fulfillment_status !== "DELIVERED" ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => deliveredMutation.mutate(invoice)}
                          disabled={deliveredMutation.isPending}
                        >
                          Mark delivered
                        </Button>
                      ) : null}
                      {invoice.lifecycle === "CONFIRMED" &&
                      invoice.return_status !== "FULLY_RETURNED" ? (
                        <Button size="sm" variant="secondary" onClick={() => openReturn(invoice)}>
                          Return
                        </Button>
                      ) : null}
                      <Link href={`/sales/${invoice.id}`}>
                        <Button size="sm" variant="secondary">
                          View / Print
                        </Button>
                      </Link>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          apiDownload(
                            `/sales/${invoice.id}/print/`,
                            `${invoice.number ?? "invoice"}.pdf`,
                          )
                        }
                      >
                        PDF
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            <Pagination
              page={page}
              hasPrevious={page > 1}
              hasNext={Boolean(salesQuery.data?.next)}
              onChange={setPage}
            />
          </>
        )}
      </Card>
    </div>
  );
}
