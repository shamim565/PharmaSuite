"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Pagination, Select, Spinner, StickyBar } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type { AdvanceRow, DailyCollectionReport, DueListResponse, DueListRow, FinancialAccount, Paginated } from "@/lib/types";

function bucketTone(bucket: DueListRow["bucket"]): "slate" | "amber" | "rose" {
  if (bucket === "current") return "slate";
  if (bucket === "days_1_30") return "amber";
  return "rose";
}

function fifoPrefill(rows: DueListRow[], amount: number): Record<string, string> {
  const result: Record<string, string> = {};
  let remaining = amount;
  const sorted = [...rows].sort((a, b) => a.due_date.localeCompare(b.due_date));
  for (const row of sorted) {
    const outstanding = Number(row.outstanding);
    const take = Math.min(remaining, outstanding);
    result[row.invoice] = take > 0 ? take.toFixed(2) : "";
    remaining -= take;
  }
  return result;
}

export default function DuesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [page, setPage] = useState(1);

  const [collectCustomer, setCollectCustomer] = useState<{ id: string; name: string } | null>(null);
  const [collectAmount, setCollectAmount] = useState("");
  const [allocations, setAllocations] = useState<Record<string, string>>({});
  const [method, setMethod] = useState("CASH");
  const [accountId, setAccountId] = useState("");
  const [reference, setReference] = useState("");

  const params = new URLSearchParams({ page_size: "25", page: String(page) });
  if (search) params.set("search", search);
  if (overdueOnly) params.set("overdue_only", "true");

  const duesQuery = useQuery({
    queryKey: ["dues", search, overdueOnly, page],
    queryFn: () => api.get<DueListResponse>(`/sales/due-list/?${params.toString()}`),
  });
  const advancesQuery = useQuery({
    queryKey: ["customer-advances"],
    queryFn: () => api.get<{ count: number; total: string; results: AdvanceRow[] }>("/customers/reports/advances/"),
  });
  const accountsQuery = useQuery({
    queryKey: ["accounts", "select"],
    queryFn: () => api.get<Paginated<FinancialAccount>>("/accounts/?page_size=50&is_active=true"),
  });
  const dailyQuery = useQuery({
    queryKey: ["daily-collection"],
    queryFn: () => api.get<DailyCollectionReport>("/payments/reports/daily-collection/"),
  });

  const collectMutation = useMutation({
    meta: { successMessage: "Payment posted" },
    mutationFn: () => {
      const rows = customerRows(collectCustomer?.id ?? "");
      const positive = Object.entries(allocations)
        .filter(([, value]) => Number(value) > 0)
        .map(([invoice, value]) => ({ invoice, amount: Number(value).toFixed(2) }));
      return api.post("/payments/", {
        customer: collectCustomer?.id,
        branch: rows[0]?.branch,
        amount: Number(collectAmount).toFixed(2),
        method,
        account: accountId,
        reference,
        allocations: positive.length > 0 ? positive : null,
      });
    },
    onSuccess: () => {
      setCollectCustomer(null);
      setCollectAmount("");
      setAllocations({});
      setReference("");
      queryClient.invalidateQueries({ queryKey: ["dues"] });
      queryClient.invalidateQueries({ queryKey: ["customer-advances"] });
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["payments"] });
      queryClient.invalidateQueries({ queryKey: ["daily-collection"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const allRows = duesQuery.data?.results ?? [];

  function customerRows(customerId: string): DueListRow[] {
    return allRows.filter((row) => row.customer === customerId);
  }

  const openCollect = (row: DueListRow) => {
    const rows = customerRows(row.customer);
    const total = rows.reduce((sum, item) => sum + Number(item.outstanding), 0);
    setCollectCustomer({ id: row.customer, name: row.customer_name });
    setCollectAmount(total.toFixed(2));
    setAllocations(fifoPrefill(rows, total));
    setMethod("CASH");
    setAccountId(accountsQuery.data?.results[0]?.id ?? "");
    setReference("");
  };

  const onCollectAmountChange = (value: string) => {
    setCollectAmount(value);
    if (collectCustomer) {
      setAllocations(fifoPrefill(customerRows(collectCustomer.id), Number(value) || 0));
    }
  };

  const allocatedTotal = Object.values(allocations).reduce((sum, value) => sum + (Number(value) || 0), 0);
  const advancePortion = Math.max((Number(collectAmount) || 0) - allocatedTotal, 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Dues & collection</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => {
                setOverdueOnly(e.target.checked);
                setPage(1);
              }}
            />
            Overdue only
          </label>
          <Input
            placeholder="Search customer…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-48"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs uppercase text-slate-500">Outstanding</p>
          <p className="text-xl font-bold text-slate-800">{formatMoney(duesQuery.data?.totals.outstanding)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs uppercase text-slate-500">Overdue</p>
          <p className="text-xl font-bold text-danger-700">{formatMoney(duesQuery.data?.totals.overdue)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs uppercase text-slate-500">Collected today</p>
          <p className="text-xl font-bold text-primary-700">{formatMoney(dailyQuery.data?.total)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs uppercase text-slate-500">Customer advances</p>
          <p className="text-xl font-bold text-sky-700">{formatMoney(advancesQuery.data?.total)}</p>
        </Card>
      </div>

      {collectCustomer ? (
        <Card>
          <CardHeader
            title={`Collect from ${collectCustomer.name}`}
            subtitle="Allocations are pre-filled oldest-first; edit any amount."
            action={
              <Button size="sm" variant="secondary" onClick={() => setCollectCustomer(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={collectMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Field label="Amount received">
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={collectAmount}
                  onChange={(e) => onCollectAmountChange(e.target.value)}
                />
              </Field>
              <Field label="Method">
                <Select value={method} onChange={(e) => setMethod(e.target.value)}>
                  <option value="CASH">Cash</option>
                  <option value="BANK">Bank</option>
                  <option value="MFS">MFS</option>
                  <option value="CHEQUE">Cheque</option>
                </Select>
              </Field>
              <Field label="Account">
                <Select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                  <option value="">Select…</option>
                  {accountsQuery.data?.results.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name} ({formatMoney(account.balance_cache)})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reference">
                <Input value={reference} onChange={(e) => setReference(e.target.value)} />
              </Field>
            </div>

            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {customerRows(collectCustomer.id).map((row) => (
                <li key={row.invoice} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                  <div>
                    <p className="text-sm font-medium">
                      {row.number} <span className="text-xs text-slate-500">due {formatDate(row.due_date)}</span>
                    </p>
                    <p className="text-xs text-slate-500">
                      Outstanding {formatMoney(row.outstanding)}
                      {row.days_overdue > 0 ? ` · ${row.days_overdue}d overdue` : ""}
                    </p>
                  </div>
                  <div className="w-32">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="0.00"
                      aria-label={`Allocate amount for invoice ${row.number}`}
                      value={allocations[row.invoice] ?? ""}
                      onChange={(e) => setAllocations({ ...allocations, [row.invoice]: e.target.value })}
                    />
                  </div>
                </li>
              ))}
            </ul>

            <StickyBar>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  <span>
                    Allocated: <strong>{formatMoney(allocatedTotal)}</strong>
                  </span>
                  <span className={advancePortion > 0 ? "text-sky-700" : "text-slate-500"}>
                    Advance: <strong>{formatMoney(advancePortion)}</strong>
                  </span>
                </div>
                <Button
                  className="w-full sm:w-auto"
                  onClick={() => collectMutation.mutate()}
                  disabled={
                    collectMutation.isPending ||
                    !accountId ||
                    Number(collectAmount) <= 0 ||
                    allocatedTotal > Number(collectAmount)
                  }
                >
                  {collectMutation.isPending ? "Posting…" : "Post receipt"}
                </Button>
              </div>
            </StickyBar>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Open invoices" subtitle={duesQuery.data ? `${duesQuery.data.count} invoice(s)` : undefined} />
        <ErrorBanner error={duesQuery.error} />
        {duesQuery.isLoading ? (
          <Spinner />
        ) : allRows.length === 0 ? (
          <EmptyState message="No outstanding invoices." />
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Invoice</th>
                    <th className="px-4 py-2">Customer</th>
                    <th className="px-4 py-2">Due</th>
                    <th className="px-4 py-2">Aging</th>
                    <th className="px-4 py-2 text-right">Outstanding</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {allRows.map((row) => (
                    <tr key={row.invoice}>
                      <td className="px-4 py-2 font-mono text-xs">{row.number}</td>
                      <td className="px-4 py-2">
                        {row.customer_name}
                        <span className="block text-xs text-slate-500">{row.phone}</span>
                      </td>
                      <td className="px-4 py-2 text-slate-500">{formatDate(row.due_date)}</td>
                      <td className="px-4 py-2">
                        <Badge tone={bucketTone(row.bucket)}>
                          {row.days_overdue > 0 ? `${row.days_overdue}d overdue` : "Current"}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-right font-medium">{formatMoney(row.outstanding)}</td>
                      <td className="px-4 py-2 text-right">
                        <Button size="sm" onClick={() => openCollect(row)} disabled={!accountsQuery.data}>
                          Collect
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="divide-y divide-slate-100 md:hidden">
              {allRows.map((row) => (
                <li key={row.invoice} className="space-y-1 p-4">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{row.customer_name}</p>
                    <Badge tone={bucketTone(row.bucket)}>
                      {row.days_overdue > 0 ? `${row.days_overdue}d` : "Current"}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    {row.number} · due {formatDate(row.due_date)} · {row.phone}
                  </p>
                  <p className="text-sm">
                    Outstanding <strong>{formatMoney(row.outstanding)}</strong>
                  </p>
                  <Button size="sm" onClick={() => openCollect(row)} disabled={!accountsQuery.data}>
                    Collect
                  </Button>
                </li>
              ))}
            </ul>
            <Pagination
              page={page}
              hasPrevious={Boolean(duesQuery.data?.previous)}
              hasNext={Boolean(duesQuery.data?.next)}
              onChange={setPage}
            />
          </>
        )}
      </Card>

      {advancesQuery.data && advancesQuery.data.count > 0 ? (
        <Card>
          <CardHeader title="Customer advances" subtitle="Unallocated receipts held on account" />
          <ul className="divide-y divide-slate-100">
            {advancesQuery.data.results.map((row) => (
              <li key={row.customer} className="flex items-center justify-between px-4 py-2 text-sm">
                <div>
                  <p className="font-medium">{row.customer_name}</p>
                  <p className="text-xs text-slate-500">
                    {row.customer_code}
                    {row.phone ? ` · ${row.phone}` : ""}
                  </p>
                </div>
                <span className="font-mono font-semibold text-sky-700">{formatMoney(row.advance)}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}
