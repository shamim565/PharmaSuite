"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Branch, Customer, FinancialAccount, Medicine, Paginated, SalesInvoice } from "@/lib/types";

type DraftRow = {
  key: number;
  medicine: string;
  qty: string;
  unit_price: string;
  line_discount: string;
  is_free_goods: boolean;
};

const newRow = (key: number): DraftRow => ({
  key,
  medicine: "",
  qty: "",
  unit_price: "",
  line_discount: "0",
  is_free_goods: false,
});

const emptyForm = { customer: "", branch: "", business_date: "", notes: "" };

function lifecycleTone(status: SalesInvoice["lifecycle"]): "green" | "slate" | "rose" {
  return status === "CONFIRMED" ? "green" : status === "CANCELLED" ? "rose" : "slate";
}

function paymentTone(status: SalesInvoice["payment_status"]): "green" | "amber" | "slate" {
  return status === "PAID" ? "green" : status === "PARTIALLY_PAID" ? "amber" : "slate";
}

export default function SalesPage() {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const [search, setSearch] = useState("");
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
  const [returnFor, setReturnFor] = useState<SalesInvoice | null>(null);
  const [returnItemId, setReturnItemId] = useState("");
  const [returnQty, setReturnQty] = useState("");
  const [returnCondition, setReturnCondition] = useState("RESELLABLE");
  const [returnReason, setReturnReason] = useState("CUSTOMER_RETURN");
  const [returnRefundMethod, setReturnRefundMethod] = useState("CUSTOMER_CREDIT");
  const [returnAccountId, setReturnAccountId] = useState("");

  const salesQuery = useQuery({
    queryKey: ["sales", search],
    queryFn: () =>
      api.get<Paginated<SalesInvoice>>(`/sales/?page_size=50&search=${encodeURIComponent(search)}`),
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
  const accountsQuery = useQuery({
    queryKey: ["accounts", "select"],
    queryFn: () => api.get<Paginated<FinancialAccount>>("/accounts/?page_size=50&is_active=true"),
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["sales"] });
    queryClient.invalidateQueries({ queryKey: ["sales-returns"] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["customers"] });
    queryClient.invalidateQueries({ queryKey: ["batches"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<SalesInvoice>("/sales/", {
        ...form,
        business_date: form.business_date || undefined,
        items: rows.map((row) => ({
          medicine: row.medicine,
          qty: row.qty,
          unit_price: row.unit_price || null,
          line_discount: row.line_discount || "0",
          is_free_goods: row.is_free_goods,
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
    mutationFn: () =>
      api.post<SalesInvoice>(`/sales/${confirmFor?.id}/confirm/`, {
        payment:
          Number(payAmount) > 0
            ? { amount: payAmount, method: payMethod, account: payAccount, reference: payReference }
            : null,
        allow_credit_override: creditOverride,
        credit_override_reason: overrideReason,
      }),
    onSuccess: () => {
      setConfirmFor(null);
      setPayAmount("");
      setPayReference("");
      setCreditOverride(false);
      setOverrideReason("");
      invalidateAll();
    },
  });

  const payMutation = useMutation({
    mutationFn: () =>
      api.post("/payments/", {
        customer: payFor?.customer,
        branch: payFor?.branch,
        amount: payAmount,
        method: payMethod,
        account: payAccount,
        reference: payReference,
        allocations: [{ invoice: payFor?.id, amount: payAmount }],
      }),
    onSuccess: () => {
      setPayFor(null);
      setPayAmount("");
      setPayReference("");
      invalidateAll();
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (invoice: SalesInvoice) =>
      api.post(`/sales/${invoice.id}/cancel/`, { reason: "Cancelled from sales register" }),
    onSuccess: () => invalidateAll(),
  });

  const returnMutation = useMutation({
    mutationFn: async () => {
      const draft = await api.post<{ id: string }>("/sales-returns/", {
        invoice: returnFor?.id,
        reason_code: returnReason,
        refund_method: returnRefundMethod,
        refund_account:
          returnRefundMethod === "CASH" || returnRefundMethod === "BANK" ? returnAccountId : null,
        items: [{ invoice_item: returnItemId, qty: returnQty, condition: returnCondition }],
      });
      return api.post(`/sales-returns/${draft.id}/confirm/`, {});
    },
    onSuccess: () => {
      setReturnFor(null);
      setReturnItemId("");
      setReturnQty("");
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
  };

  const selectedReturnItem = returnFor?.items.find((item) => item.id === returnItemId);

  const openConfirm = (invoice: SalesInvoice) => {
    setConfirmFor(invoice);
    setPayAmount("");
    setPayMethod("CASH");
    setPayAccount(accountsQuery.data?.results[0]?.id ?? "");
    setCreditOverride(false);
    setOverrideReason("");
  };

  const openPay = (invoice: SalesInvoice) => {
    setPayFor(invoice);
    setPayAmount(invoice.outstanding);
    setPayMethod("CASH");
    setPayAccount(accountsQuery.data?.results[0]?.id ?? "");
  };

  const updateRow = (key: number, patch: Partial<DraftRow>) => {
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  const confirmError = confirmMutation.error;
  const creditBlocked = confirmError instanceof ApiError && confirmError.code === "CREDIT_LIMIT_EXCEEDED";

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
                <Select value={form.customer} onChange={(e) => setForm({ ...form, customer: e.target.value })} required>
                  <option value="">Select…</option>
                  {customersQuery.data?.results.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.name} ({customer.balance_cache})
                    </option>
                  ))}
                </Select>
              </Field>
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
              <Field label="Date" error={fieldError("business_date")}>
                <Input
                  type="date"
                  value={form.business_date}
                  onChange={(e) => setForm({ ...form, business_date: e.target.value })}
                />
              </Field>
            </div>

            <div className="space-y-2">
              {rows.map((row, index) => (
                <div key={row.key} className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 p-3 lg:grid-cols-6">
                  <div className="col-span-2">
                    <Field label={`Medicine ${index + 1}`}>
                      <Select value={row.medicine} onChange={(e) => updateRow(row.key, { medicine: e.target.value })} required>
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
                  <label className="flex items-end gap-2 pb-2 text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={row.is_free_goods}
                      onChange={(e) => updateRow(row.key, { is_free_goods: e.target.checked })}
                    />
                    Free goods
                  </label>
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

            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Save draft"}
            </Button>
          </form>
        </Card>
      ) : null}

      {confirmFor ? (
        <Card>
          <CardHeader
            title={`Confirm invoice — ${confirmFor.customer_name}`}
            subtitle={`Total ${confirmFor.grand_total}`}
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
                <Input type="number" step="0.01" min="0" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} />
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
                      {account.name} ({account.balance_cache})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reference">
                <Input value={payReference} onChange={(e) => setPayReference(e.target.value)} />
              </Field>
            </div>
            {creditBlocked && hasPerm("SALE_OVERRIDE_CREDIT") ? (
              <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <label className="flex items-center gap-2 text-sm text-amber-800">
                  <input type="checkbox" checked={creditOverride} onChange={(e) => setCreditOverride(e.target.checked)} />
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
            subtitle={`Outstanding ${payFor.outstanding} on ${payFor.number}`}
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
                <Input type="number" step="0.01" min="0.01" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} />
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
                      {account.name} ({account.balance_cache})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reference">
                <Input value={payReference} onChange={(e) => setPayReference(e.target.value)} />
              </Field>
            </div>
            <Button onClick={() => payMutation.mutate()} disabled={payMutation.isPending || !payAccount || !payAmount}>
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
                          {item.medicine_name} · {item.batch_number} · returnable {returnable.toFixed(3)}
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
                <Select value={returnCondition} onChange={(e) => setReturnCondition(e.target.value)}>
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
                <Select value={returnRefundMethod} onChange={(e) => setReturnRefundMethod(e.target.value)}>
                  <option value="CUSTOMER_CREDIT">Customer credit</option>
                  <option value="ADJUST_DUES">Adjust dues</option>
                  <option value="CASH">Cash refund</option>
                  <option value="BANK">Bank refund</option>
                </Select>
              </Field>
              {returnRefundMethod === "CASH" || returnRefundMethod === "BANK" ? (
                <Field label="Refund account">
                  <Select value={returnAccountId} onChange={(e) => setReturnAccountId(e.target.value)}>
                    <option value="">Select…</option>
                    {accountsQuery.data?.results.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name} ({account.balance_cache})
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
            </div>
            {selectedReturnItem ? (
              <p className="text-xs text-slate-500">
                Returnable now:{" "}
                {(Number(selectedReturnItem.qty) - Number(selectedReturnItem.returned_qty ?? 0)).toFixed(3)} · unit
                price {selectedReturnItem.unit_price}
              </p>
            ) : null}
            <Button
              onClick={() => returnMutation.mutate()}
              disabled={
                returnMutation.isPending ||
                !returnItemId ||
                !returnQty ||
                ((returnRefundMethod === "CASH" || returnRefundMethod === "BANK") && !returnAccountId)
              }
            >
              {returnMutation.isPending ? "Processing…" : "Create & confirm return"}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Sales register"
          subtitle={salesQuery.data ? `${salesQuery.data.count} invoice(s)` : undefined}
          action={
            <Input
              placeholder="Search number, customer…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-56"
            />
          }
        />
        <ErrorBanner error={salesQuery.error} />
        {salesQuery.isLoading ? (
          <Spinner />
        ) : !salesQuery.data || salesQuery.data.results.length === 0 ? (
          <EmptyState message="No invoices yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {salesQuery.data.results.map((invoice) => (
              <li key={invoice.id} className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">
                      <Link href={`/sales/${invoice.id}`} className="text-emerald-700 hover:underline">
                        {invoice.number ?? "Draft"}
                      </Link>{" "}
                      <span className="text-xs text-slate-400">{invoice.customer_name}</span>
                    </p>
                    <p className="text-xs text-slate-500">
                      {invoice.business_date} · {invoice.items.length} line(s)
                      {invoice.due_date ? ` · due ${invoice.due_date}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={lifecycleTone(invoice.lifecycle)}>{invoice.lifecycle}</Badge>
                    <Badge tone={paymentTone(invoice.payment_status)}>{invoice.payment_status}</Badge>
                    {invoice.credit_override ? <Badge tone="amber">Credit override</Badge> : null}
                  </div>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm">
                    Total <strong>{invoice.grand_total}</strong> · Paid {invoice.paid_total} ·{" "}
                    <span className={Number(invoice.outstanding) > 0 ? "text-rose-700" : "text-emerald-700"}>
                      Outstanding {invoice.outstanding}
                    </span>
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {invoice.lifecycle === "DRAFT" ? (
                      <Button size="sm" onClick={() => openConfirm(invoice)} disabled={!accountsQuery.data}>
                        Confirm
                      </Button>
                    ) : null}
                    {invoice.lifecycle === "CONFIRMED" && Number(invoice.outstanding) > 0 ? (
                      <Button size="sm" variant="secondary" onClick={() => openPay(invoice)}>
                        Receive payment
                      </Button>
                    ) : null}
                    {invoice.lifecycle === "CONFIRMED" && Number(invoice.paid_total) === 0 && hasPerm("SALE_CANCEL") ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => cancelMutation.mutate(invoice)}
                        disabled={cancelMutation.isPending}
                      >
                        Cancel
                      </Button>
                    ) : null}
                    {invoice.lifecycle === "CONFIRMED" && invoice.return_status !== "FULLY_RETURNED" ? (
                      <Button size="sm" variant="secondary" onClick={() => openReturn(invoice)}>
                        Return
                      </Button>
                    ) : null}
                    <Link href={`/sales/${invoice.id}`}>
                      <Button size="sm" variant="secondary">
                        View / Print
                      </Button>
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
