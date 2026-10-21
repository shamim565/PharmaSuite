"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { FormEvent, useState } from "react";

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
import { AttachmentPanel } from "@/components/attachments";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type {
  Branch,
  FinancialAccount,
  Medicine,
  Paginated,
  Purchase,
  Supplier,
} from "@/lib/types";

type DraftRow = {
  key: number;
  medicine: string;
  batch_number: string;
  manufacturing_date: string;
  expiry_date: string;
  qty_entered: string;
  bonus_qty_entered: string;
  unit_cost: string;
  line_discount: string;
};

const newRow = (key: number): DraftRow => ({
  key,
  medicine: "",
  batch_number: "",
  manufacturing_date: "",
  expiry_date: "",
  qty_entered: "",
  bonus_qty_entered: "",
  unit_cost: "",
  line_discount: "0",
});

const emptyForm = {
  supplier: "",
  branch: "",
  supplier_invoice_number: "",
  supplier_invoice_date: "",
  business_date: "",
  notes: "",
};

function lifecycleTone(status: Purchase["lifecycle"]): "green" | "slate" | "rose" {
  return status === "CONFIRMED" ? "green" : status === "CANCELLED" ? "rose" : "slate";
}

function paymentTone(status: Purchase["payment_status"]): "green" | "amber" | "slate" {
  return status === "PAID" ? "green" : status === "PARTIALLY_PAID" ? "amber" : "slate";
}

export default function PurchasesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [rows, setRows] = useState<DraftRow[]>([newRow(1)]);
  const [rowSeq, setRowSeq] = useState(2);
  const debouncedSearch = useDebouncedValue(search);

  // action panels
  const [confirmFor, setConfirmFor] = useState<Purchase | null>(null);
  const [payFor, setPayFor] = useState<Purchase | null>(null);
  const [returnFor, setReturnFor] = useState<Purchase | null>(null);
  const [cancelFor, setCancelFor] = useState<Purchase | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [filesFor, setFilesFor] = useState<Purchase | null>(null);
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("CASH");
  const [payAccount, setPayAccount] = useState("");
  const [payReference, setPayReference] = useState("");
  const [returnItem, setReturnItem] = useState("");
  const [returnQty, setReturnQty] = useState("");
  const [returnReason, setReturnReason] = useState("DAMAGED");

  const purchaseParams = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) purchaseParams.set("search", debouncedSearch);

  const purchasesQuery = useQuery({
    queryKey: ["purchases", debouncedSearch, page],
    queryFn: () => api.get<Paginated<Purchase>>(`/purchases/?${purchaseParams.toString()}`),
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
  const accountsQuery = useQuery({
    queryKey: ["accounts", "select"],
    queryFn: () => api.get<Paginated<FinancialAccount>>("/accounts/?page_size=50&is_active=true"),
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["purchases"] });
    queryClient.invalidateQueries({ queryKey: ["batches"] });
    queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const createMutation = useMutation({
    meta: { successMessage: "Purchase saved as draft" },
    mutationFn: () =>
      api.post<Purchase>("/purchases/", {
        ...form,
        business_date: form.business_date || undefined,
        items: rows.map((row) => ({
          medicine: row.medicine,
          batch_number: row.batch_number,
          manufacturing_date: row.manufacturing_date || null,
          expiry_date: row.expiry_date || null,
          qty_entered: row.qty_entered,
          bonus_qty_entered: row.bonus_qty_entered || "0",
          unit_cost: row.unit_cost,
          line_discount: row.line_discount || "0",
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
    meta: { successMessage: "Purchase confirmed" },
    mutationFn: () =>
      api.post<Purchase>(`/purchases/${confirmFor?.id}/confirm/`, {
        payment:
          Number(payAmount) > 0
            ? { amount: payAmount, method: payMethod, account: payAccount, reference: payReference }
            : null,
      }),
    onSuccess: () => {
      setConfirmFor(null);
      setPayAmount("");
      setPayReference("");
      invalidateAll();
    },
  });

  const payMutation = useMutation({
    meta: { successMessage: "Payment posted" },
    mutationFn: () =>
      api.post("/supplier-payments/", {
        supplier: payFor?.supplier,
        branch: payFor?.branch,
        amount: payAmount,
        method: payMethod,
        account: payAccount,
        reference: payReference,
        allocations: [{ purchase: payFor?.id, amount: payAmount }],
      }),
    onSuccess: () => {
      setPayFor(null);
      setPayAmount("");
      setPayReference("");
      invalidateAll();
    },
  });

  const returnMutation = useMutation({
    meta: { successMessage: "Return created and confirmed" },
    mutationFn: async () => {
      const draft = await api.post<{ id: string }>("/purchase-returns/", {
        purchase: returnFor?.id,
        reason_code: returnReason,
        items: [{ purchase_item: returnItem, qty: returnQty }],
      });
      return api.post(`/purchase-returns/${draft.id}/confirm/`, {});
    },
    onSuccess: () => {
      setReturnFor(null);
      setReturnItem("");
      setReturnQty("");
      invalidateAll();
    },
  });

  const cancelMutation = useMutation({
    meta: { successMessage: "Purchase cancelled" },
    mutationFn: () =>
      api.post(`/purchases/${cancelFor?.id}/cancel/`, {
        reason: cancelReason || "Cancelled from purchase register",
      }),
    onSuccess: () => {
      setCancelFor(null);
      setCancelReason("");
      invalidateAll();
    },
  });

  const openConfirm = (purchase: Purchase) => {
    setConfirmFor(purchase);
    setPayAmount("");
    setPayMethod("CASH");
    setPayAccount(accountsQuery.data?.results[0]?.id ?? "");
  };

  const openPay = (purchase: Purchase) => {
    setPayFor(purchase);
    setPayAmount(purchase.outstanding);
    setPayMethod("CASH");
    setPayAccount(accountsQuery.data?.results[0]?.id ?? "");
  };

  const openReturn = (purchase: Purchase) => {
    setReturnFor(purchase);
    setReturnReason("DAMAGED");
    const firstReturnable = purchase.items.find(
      (item) =>
        Number(item.qty_base) + Number(item.bonus_qty_base) - Number(item.returned_qty_base) > 0,
    );
    setReturnItem(firstReturnable?.id ?? "");
    setReturnQty("");
  };

  const updateRow = (key: number, patch: Partial<DraftRow>) => {
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  const selectedReturnItem = returnFor?.items.find((item) => item.id === returnItem);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Purchases</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "New purchase"}
        </Button>
      </div>

      {showForm ? (
        <Card>
          <CardHeader title="New purchase" subtitle="Stock and payable are posted on confirm." />
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
              <Field label="Supplier invoice #" error={fieldError("supplier_invoice_number")}>
                <Input
                  value={form.supplier_invoice_number}
                  onChange={(e) => setForm({ ...form, supplier_invoice_number: e.target.value })}
                  required
                />
              </Field>
              <Field label="Invoice date" error={fieldError("supplier_invoice_date")}>
                <Input
                  type="date"
                  value={form.supplier_invoice_date}
                  onChange={(e) => setForm({ ...form, supplier_invoice_date: e.target.value })}
                  required
                />
              </Field>
            </div>

            <div className="space-y-2">
              {rows.map((row, index) => (
                <div
                  key={row.key}
                  className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 p-3 lg:grid-cols-8"
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
                  <Field label="Batch #">
                    <Input
                      value={row.batch_number}
                      onChange={(e) => updateRow(row.key, { batch_number: e.target.value })}
                      required
                    />
                  </Field>
                  <Field label="Mfg date">
                    <Input
                      type="date"
                      value={row.manufacturing_date}
                      onChange={(e) => updateRow(row.key, { manufacturing_date: e.target.value })}
                    />
                  </Field>
                  <Field label="Expiry">
                    <Input
                      type="date"
                      value={row.expiry_date}
                      onChange={(e) => updateRow(row.key, { expiry_date: e.target.value })}
                    />
                  </Field>
                  <Field label="Qty">
                    <Input
                      type="number"
                      step="0.001"
                      min="0.001"
                      value={row.qty_entered}
                      onChange={(e) => updateRow(row.key, { qty_entered: e.target.value })}
                      required
                    />
                  </Field>
                  <Field label="Bonus">
                    <Input
                      type="number"
                      step="0.001"
                      min="0"
                      value={row.bonus_qty_entered}
                      onChange={(e) => updateRow(row.key, { bonus_qty_entered: e.target.value })}
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
                  <div className="col-span-2 flex items-end lg:col-span-8">
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

            <Button type="submit" className="w-full lg:w-auto" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Save draft"}
            </Button>
          </form>
        </Card>
      ) : null}

      {/* Confirm panel */}
      {confirmFor ? (
        <Card>
          <CardHeader
            title={`Confirm purchase ${confirmFor.supplier_invoice_number}`}
            subtitle={`${confirmFor.supplier_name} · total ${formatMoney(confirmFor.grand_total)}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setConfirmFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={confirmMutation.error} />
            <p className="text-sm text-slate-600">
              Optionally record a payment now. Leave the amount at 0 to confirm on credit.
            </p>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Field label="Pay now (amount)">
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
            <Button
              onClick={() => confirmMutation.mutate()}
              disabled={confirmMutation.isPending || (Number(payAmount) > 0 && !payAccount)}
            >
              {confirmMutation.isPending ? "Confirming…" : "Confirm purchase"}
            </Button>
          </div>
        </Card>
      ) : null}

      {/* Pay panel */}
      {payFor ? (
        <Card>
          <CardHeader
            title={`Pay supplier — ${payFor.supplier_name}`}
            subtitle={`Outstanding ${formatMoney(payFor.outstanding)}`}
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
              {payMutation.isPending ? "Posting…" : "Post payment"}
            </Button>
          </div>
        </Card>
      ) : null}

      {/* Return panel */}
      {returnFor ? (
        <Card>
          <CardHeader
            title={`Return to supplier — ${returnFor.number}`}
            subtitle="Stock decreases and a debit note is issued."
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
                <Field label="Purchase line">
                  <Select value={returnItem} onChange={(e) => setReturnItem(e.target.value)}>
                    <option value="">Select…</option>
                    {returnFor.items.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.medicine_name} · {item.batch_number} · returnable{" "}
                        {formatQty(
                          Number(item.qty_base) +
                            Number(item.bonus_qty_base) -
                            Number(item.returned_qty_base),
                        )}
                      </option>
                    ))}
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
              <Field label="Reason">
                <Select value={returnReason} onChange={(e) => setReturnReason(e.target.value)}>
                  <option value="DAMAGED">Damaged</option>
                  <option value="EXPIRED">Expired</option>
                  <option value="NEAR_EXPIRY_AGREEMENT">Near-expiry agreement</option>
                  <option value="WRONG_ITEM">Wrong item</option>
                  <option value="OVER_SUPPLY">Over supply</option>
                </Select>
              </Field>
            </div>
            {selectedReturnItem ? (
              <p className="text-xs text-slate-500">
                Returnable now:{" "}
                {formatQty(
                  Number(selectedReturnItem.qty_base) +
                    Number(selectedReturnItem.bonus_qty_base) -
                    Number(selectedReturnItem.returned_qty_base),
                )}
              </p>
            ) : null}
            <Button
              onClick={() => returnMutation.mutate()}
              disabled={returnMutation.isPending || !returnItem || !returnQty}
            >
              {returnMutation.isPending ? "Processing…" : "Create & confirm return"}
            </Button>
          </div>
        </Card>
      ) : null}

      {cancelFor ? (
        <Card>
          <CardHeader
            title={`Cancel purchase ${cancelFor.number ?? ""}`}
            subtitle="Allowed only when unpaid, unreturned and stock is unconsumed."
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
              {cancelMutation.isPending ? "Cancelling…" : "Cancel purchase"}
            </Button>
          </div>
        </Card>
      ) : null}

      {filesFor ? (
        <Card>
          <CardHeader
            title={`Documents — ${filesFor.number ?? filesFor.supplier_invoice_number}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setFilesFor(null)}>
                Close
              </Button>
            }
          />
          <div className="p-4">
            <AttachmentPanel
              ownerType="PURCHASE"
              ownerId={filesFor.id}
              title="Supplier invoice & documents"
            />
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Purchase register"
          subtitle={purchasesQuery.data ? `${purchasesQuery.data.count} purchase(s)` : undefined}
          action={
            <Input
              placeholder="Search number, invoice, supplier…"
              aria-label="Search purchases"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-56"
            />
          }
        />
        <ErrorBanner error={purchasesQuery.error} />
        {purchasesQuery.isLoading ? (
          <Spinner />
        ) : !purchasesQuery.data || purchasesQuery.data.results.length === 0 ? (
          <EmptyState message="No purchases yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {purchasesQuery.data.results.map((purchase) => (
              <li key={purchase.id} className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">
                      {purchase.number ? (
                        <Link href={`/purchases/${purchase.id}`} className="hover:underline">
                          {purchase.number}
                        </Link>
                      ) : (
                        "Draft"
                      )}{" "}
                      <span className="text-xs text-slate-500">
                        {purchase.supplier_invoice_number}
                      </span>
                    </p>
                    <p className="text-xs text-slate-500">
                      {purchase.supplier_name} · {formatDate(purchase.business_date)} ·{" "}
                      {purchase.items.length} line(s)
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={lifecycleTone(purchase.lifecycle)}>{purchase.lifecycle}</Badge>
                    <Badge tone={paymentTone(purchase.payment_status)}>
                      {purchase.payment_status}
                    </Badge>
                    {purchase.return_status !== "NONE" ? (
                      <Badge tone="amber">{purchase.return_status}</Badge>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm">
                    Total <strong>{formatMoney(purchase.grand_total)}</strong> · Paid{" "}
                    {formatMoney(purchase.paid_total)} ·{" "}
                    <span
                      className={
                        Number(purchase.outstanding) > 0 ? "text-danger-700" : "text-primary-700"
                      }
                    >
                      Outstanding {formatMoney(purchase.outstanding)}
                    </span>
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {purchase.lifecycle === "DRAFT" ? (
                      <Button
                        size="sm"
                        onClick={() => openConfirm(purchase)}
                        disabled={!accountsQuery.data}
                      >
                        Confirm
                      </Button>
                    ) : null}
                    {purchase.lifecycle === "CONFIRMED" && Number(purchase.outstanding) > 0 ? (
                      <Button size="sm" variant="secondary" onClick={() => openPay(purchase)}>
                        Pay
                      </Button>
                    ) : null}
                    {purchase.lifecycle === "CONFIRMED" &&
                    purchase.return_status !== "FULLY_RETURNED" ? (
                      <Button size="sm" variant="secondary" onClick={() => openReturn(purchase)}>
                        Return
                      </Button>
                    ) : null}
                    {purchase.lifecycle === "CONFIRMED" &&
                    Number(purchase.paid_total) === 0 &&
                    purchase.return_status === "NONE" ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setCancelFor(purchase);
                          setCancelReason("");
                        }}
                      >
                        Cancel
                      </Button>
                    ) : null}
                    <Button size="sm" variant="secondary" onClick={() => setFilesFor(purchase)}>
                      Files
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        {purchasesQuery.data && purchasesQuery.data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(purchasesQuery.data.previous)}
            hasNext={Boolean(purchasesQuery.data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
