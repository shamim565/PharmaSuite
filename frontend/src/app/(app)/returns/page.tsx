"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Pagination, Select, Spinner, Tabs } from "@/components/ui";
import { MedicineCombobox } from "@/components/medicine-combobox";
import { api, newIdempotencyKey } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type {
  Branch,
  Customer,
  FinancialAccount,
  MedicineBatch,
  Paginated,
  SalesReturn,
} from "@/lib/types";

const TABS = ["Sales returns", "Purchase returns"] as const;
type Tab = (typeof TABS)[number];

function reasonTone(reason: string): "slate" | "amber" | "rose" {
  if (reason === "DAMAGED" || reason === "EXPIRED" || reason === "EXPIRED_AT_CUSTOMER") return "rose";
  if (reason === "WRONG_ITEM" || reason === "OVER_SUPPLY") return "amber";
  return "slate";
}

function DirectReturnForm() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [customer, setCustomer] = useState("");
  const [branch, setBranch] = useState("");
  const [reasonCode, setReasonCode] = useState("CUSTOMER_RETURN");
  const [refundMethod, setRefundMethod] = useState("CUSTOMER_CREDIT");
  const [refundAccount, setRefundAccount] = useState("");
  const [notes, setNotes] = useState("");
  const [medicine, setMedicine] = useState("");
  const [batch, setBatch] = useState("");
  const [qty, setQty] = useState("");
  const [condition, setCondition] = useState("RESELLABLE");
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey());

  const customersQuery = useQuery({
    queryKey: ["customers", "select"],
    queryFn: () => api.get<Paginated<Customer>>("/customers/?page_size=200&is_active=true"),
    enabled: showForm,
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=100&status=ACTIVE"),
    enabled: showForm,
  });
  const accountsQuery = useQuery({
    queryKey: ["accounts", "select"],
    queryFn: () => api.get<Paginated<FinancialAccount>>("/accounts/?page_size=50&is_active=true"),
    enabled: showForm,
  });
  const batchesQuery = useQuery({
    queryKey: ["batches", "direct-return", branch, medicine],
    queryFn: () =>
      api.get<Paginated<MedicineBatch>>(
        `/batches/?page_size=100&branch=${branch}&medicine=${medicine}`,
      ),
    enabled: showForm && Boolean(branch && medicine),
  });

  const directMutation = useMutation({
    meta: { successMessage: "Return created and confirmed" },
    mutationFn: async () => {
      const draft = await api.postWithKey<{ id: string }>(
        "/sales-returns/direct/",
        {
          customer,
          branch,
          reason_code: reasonCode,
          refund_method: refundMethod,
          refund_account:
            refundMethod === "CASH" || refundMethod === "BANK" ? refundAccount : null,
          notes,
          items: [{ medicine, batch, qty, condition }],
        },
        idempotencyKey,
      );
      return api.post(`/sales-returns/${draft.id}/confirm/`, {});
    },
    onSuccess: () => {
      setCustomer("");
      setMedicine("");
      setBatch("");
      setQty("");
      setNotes("");
      setIdempotencyKey(newIdempotencyKey());
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["sales-returns"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  return (
    <Card>
      <CardHeader
        title="Return without invoice"
        subtitle="Goods are returned without an original sale in this system; stock is added back and the customer is credited."
        action={
          <Button size="sm" variant="secondary" onClick={() => setShowForm((value) => !value)}>
            {showForm ? "Close" : "New direct return"}
          </Button>
        }
      />
      {showForm ? (
        <div className="space-y-3 p-4">
          <ErrorBanner error={directMutation.error} />
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Field label="Customer">
              <Select value={customer} onChange={(e) => setCustomer(e.target.value)}>
                <option value="">Select…</option>
                {customersQuery.data?.results.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name} ({row.code})
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Branch">
              <Select
                value={branch}
                onChange={(e) => {
                  setBranch(e.target.value);
                  setBatch("");
                }}
              >
                <option value="">Select…</option>
                {branchesQuery.data?.results.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Reason">
              <Select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)}>
                <option value="CUSTOMER_RETURN">Customer return</option>
                <option value="DAMAGED">Damaged</option>
                <option value="EXPIRED_AT_CUSTOMER">Expired at customer</option>
                <option value="WRONG_ITEM">Wrong item</option>
                <option value="EXCESS_SUPPLY">Excess supply</option>
              </Select>
            </Field>
            <Field label="Condition">
              <Select value={condition} onChange={(e) => setCondition(e.target.value)}>
                <option value="RESELLABLE">Resellable (restock)</option>
                <option value="DAMAGED">Damaged (quarantine)</option>
                <option value="EXPIRED">Expired (quarantine)</option>
              </Select>
            </Field>
            <div className="col-span-2">
              <Field label="Medicine">
                <MedicineCombobox
                  value={medicine}
                  onChange={(id) => {
                    setMedicine(id);
                    setBatch("");
                  }}
                />
              </Field>
            </div>
            <Field label="Batch (branch stock)">
              <Select
                value={batch}
                onChange={(e) => setBatch(e.target.value)}
                disabled={!medicine || !branch}
              >
                <option value="">Select…</option>
                {batchesQuery.data?.results.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.batch_number} · exp {row.expiry_date ? formatDate(row.expiry_date) : "—"}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Quantity">
              <Input
                type="number"
                step="0.001"
                min="0.001"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
              />
            </Field>
            <Field label="Refund method">
              <Select value={refundMethod} onChange={(e) => setRefundMethod(e.target.value)}>
                <option value="CUSTOMER_CREDIT">Customer credit</option>
                <option value="ADJUST_DUES">Adjust dues</option>
                <option value="CASH">Cash refund</option>
                <option value="BANK">Bank refund</option>
              </Select>
            </Field>
            {refundMethod === "CASH" || refundMethod === "BANK" ? (
              <Field label="Refund account">
                <Select value={refundAccount} onChange={(e) => setRefundAccount(e.target.value)}>
                  <option value="">Select…</option>
                  {accountsQuery.data?.results.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.name}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : null}
            <div className="col-span-2">
              <Field label="Notes">
                <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
              </Field>
            </div>
          </div>
          <Button
            onClick={() => directMutation.mutate()}
            disabled={
              directMutation.isPending ||
              !customer ||
              !branch ||
              !medicine ||
              !batch ||
              !qty ||
              ((refundMethod === "CASH" || refundMethod === "BANK") && !refundAccount)
            }
          >
            {directMutation.isPending ? "Processing…" : "Create & confirm return"}
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

export default function ReturnsPage() {
  const { hasPerm } = useAuth();
  const [tab, setTab] = useState<Tab>("Sales returns");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(search);

  const salesParams = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) salesParams.set("search", debouncedSearch);

  const salesQuery = useQuery({
    queryKey: ["sales-returns", debouncedSearch, page],
    queryFn: () => api.get<Paginated<SalesReturn>>(`/sales-returns/?${salesParams.toString()}`),
    enabled: tab === "Sales returns",
  });
  const purchaseQuery = useQuery({
    queryKey: ["purchase-returns", debouncedSearch, page],
    queryFn: () => api.get<Paginated<{ id: string; number: string; purchase_number: string; supplier_name: string; business_date: string; reason_code: string; status: string; grand_total: string }>>(
      `/purchase-returns/?${salesParams.toString()}`,
    ),
    enabled: tab === "Purchase returns",
  });

  const visibleTabs = TABS.filter((item) => {
    if (item === "Sales returns") return hasPerm("SRET_VIEW");
    return hasPerm("PRET_VIEW");
  });
  const activeTab = visibleTabs.includes(tab) ? tab : visibleTabs[0];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Returns</h1>
        <Input
          placeholder="Search number, invoice, supplier…"
          aria-label="Search returns"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-56"
        />
      </div>

      <Tabs
        tabs={visibleTabs}
        active={activeTab}
        onChange={(item) => {
          setTab(item);
          setPage(1);
        }}
      />

      {activeTab === "Sales returns" && hasPerm("SRET_NO_INVOICE") ? <DirectReturnForm /> : null}

      {activeTab === "Sales returns" ? (
        <Card>
          <CardHeader
            title="Sales returns & credit notes"
            subtitle={salesQuery.data ? `${salesQuery.data.count} return(s)` : undefined}
          />
          <ErrorBanner error={salesQuery.error} />
          {salesQuery.isLoading ? (
            <Spinner />
          ) : !salesQuery.data || salesQuery.data.results.length === 0 ? (
            <EmptyState message="No sales returns yet. Use the Return action on a confirmed invoice." />
          ) : (
            <ul className="divide-y divide-slate-100">
              {salesQuery.data.results.map((salesReturn) => (
                <li key={salesReturn.id} className="space-y-1 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium">
                        {salesReturn.number ?? "Draft"}{" "}
                        <span className="text-xs text-slate-500">
                          {salesReturn.invoice && salesReturn.invoice_number ? (
                            <>
                              invoice{" "}
                              <Link
                                href={`/sales/${salesReturn.invoice}`}
                                className="text-primary-700 hover:underline"
                              >
                                {salesReturn.invoice_number}
                              </Link>
                            </>
                          ) : (
                            "direct return"
                          )}
                        </span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {salesReturn.customer_name} · {formatDate(salesReturn.business_date)} ·{" "}
                        {salesReturn.refund_method.replace("_", " ").toLowerCase()} · {salesReturn.items.length} line(s)
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={reasonTone(salesReturn.reason_code)}>{salesReturn.reason_code.replace(/_/g, " ")}</Badge>
                      {salesReturn.status === "CONFIRMED" ? (
                        <Badge tone="green">Confirmed</Badge>
                      ) : (
                        <Badge tone="slate">{salesReturn.status}</Badge>
                      )}
                      <span className="font-mono font-semibold">{formatMoney(salesReturn.grand_total)}</span>
                    </div>
                  </div>
                  {salesReturn.items.some((item) => !item.restocked) ? (
                    <p className="text-xs text-amber-700">Some lines went to quarantine (damaged/expired).</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {salesQuery.data && salesQuery.data.count > 0 ? (
            <Pagination
              page={page}
              hasPrevious={Boolean(salesQuery.data.previous)}
              hasNext={Boolean(salesQuery.data.next)}
              onChange={setPage}
            />
          ) : null}
        </Card>
      ) : null}

      {activeTab === "Purchase returns" ? (
        <Card>
          <CardHeader
            title="Purchase returns & debit notes"
            subtitle={purchaseQuery.data ? `${purchaseQuery.data.count} return(s)` : undefined}
          />
          <ErrorBanner error={purchaseQuery.error} />
          {purchaseQuery.isLoading ? (
            <Spinner />
          ) : !purchaseQuery.data || purchaseQuery.data.results.length === 0 ? (
            <EmptyState message="No purchase returns yet. Use the Return action on a confirmed purchase." />
          ) : (
            <ul className="divide-y divide-slate-100">
              {purchaseQuery.data.results.map((purchaseReturn) => (
                <li key={purchaseReturn.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                  <div>
                    <p className="font-medium">
                      {purchaseReturn.number}{" "}
                      <span className="text-xs text-slate-500">purchase {purchaseReturn.purchase_number}</span>
                    </p>
                    <p className="text-xs text-slate-500">
                      {purchaseReturn.supplier_name} · {formatDate(purchaseReturn.business_date)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={reasonTone(purchaseReturn.reason_code)}>
                      {purchaseReturn.reason_code.replace(/_/g, " ")}
                    </Badge>
                    <Badge tone={purchaseReturn.status === "CONFIRMED" ? "green" : "slate"}>
                      {purchaseReturn.status}
                    </Badge>
                    <span className="font-mono font-semibold">{formatMoney(purchaseReturn.grand_total)}</span>
                    <Link
                      href="/purchases"
                      className="inline-flex min-h-[36px] items-center rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
                    >
                      Open purchases
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {purchaseQuery.data && purchaseQuery.data.count > 0 ? (
            <Pagination
              page={page}
              hasPrevious={Boolean(purchaseQuery.data.previous)}
              hasNext={Boolean(purchaseQuery.data.next)}
              onChange={setPage}
            />
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
