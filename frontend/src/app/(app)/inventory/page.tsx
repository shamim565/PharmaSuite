"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Input,
  Pagination,
  Select,
  Spinner,
  Tabs,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type {
  ExpiryReportRow,
  InventoryEntryType,
  InventoryTransaction,
  Paginated,
  StockSummaryRow,
} from "@/lib/types";

const TABS = ["Stock", "Ledger", "Alerts"] as const;
type Tab = (typeof TABS)[number];

const ENTRY_TYPES: InventoryEntryType[] = [
  "OPENING",
  "PURCHASE",
  "BONUS",
  "SALE",
  "SALES_RETURN",
  "PURCHASE_RETURN",
  "ADJUSTMENT",
  "BONUS_ISSUE",
  "DAMAGE",
  "EXPIRY",
  "TRANSFER",
  "REVERSAL",
];

function StockTab() {
  const [search, setSearch] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  const debouncedSearch = useDebouncedValue(search);

  const params = new URLSearchParams();
  if (debouncedSearch) params.set("search", debouncedSearch);
  if (lowOnly) params.set("low_stock", "true");

  const { data, isLoading, error } = useQuery({
    queryKey: ["stock-summary", debouncedSearch, lowOnly],
    queryFn: () =>
      api.get<{ count: number; results: StockSummaryRow[] }>(
        `/inventory/summary/?${params.toString()}`,
      ),
  });

  return (
    <Card>
      <CardHeader
        title="Stock on hand"
        subtitle={data ? `${data.count} medicine/branch line(s)` : undefined}
        action={
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={lowOnly}
                onChange={(e) => setLowOnly(e.target.checked)}
              />
              Low stock only
            </label>
            <Input
              placeholder="Search medicine…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-44"
            />
          </div>
        }
      />
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : !data || data.results.length === 0 ? (
        <EmptyState message="No stock matches." />
      ) : (
        <>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Medicine</th>
                  <th className="px-4 py-2">Branch</th>
                  <th className="px-4 py-2 text-right">On hand</th>
                  <th className="px-4 py-2 text-right">Promo</th>
                  <th className="px-4 py-2 text-right">Quarantine</th>
                  <th className="px-4 py-2 text-right">Reorder</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={`${row.branch}-${row.medicine}`}>
                    <td className="px-4 py-2">
                      <span className="font-medium">{row.medicine_name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">{row.medicine_code}</span>
                    </td>
                    <td className="px-4 py-2 text-slate-500">{row.branch_name}</td>
                    <td className="px-4 py-2 text-right font-medium">
                      {formatQty(row.qty_on_hand)}
                    </td>
                    <td className="px-4 py-2 text-right text-slate-500">
                      {formatQty(row.qty_promo)}
                    </td>
                    <td className="px-4 py-2 text-right text-slate-500">
                      {formatQty(row.qty_quarantine)}
                    </td>
                    <td className="px-4 py-2 text-right text-slate-500">
                      {formatQty(row.reorder_level)}
                    </td>
                    <td className="space-x-1 px-4 py-2">
                      {row.is_out_of_stock ? <Badge tone="rose">Out of stock</Badge> : null}
                      {!row.is_out_of_stock && row.is_low_stock ? (
                        <Badge tone="amber">Low</Badge>
                      ) : null}
                      {!row.is_out_of_stock && !row.is_low_stock ? (
                        <Badge tone="green">OK</Badge>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="divide-y divide-slate-100 md:hidden">
            {data.results.map((row) => (
              <li key={`${row.branch}-${row.medicine}`} className="space-y-1 p-4">
                <div className="flex items-center justify-between">
                  <p className="font-medium">{row.medicine_name}</p>
                  {row.is_out_of_stock ? (
                    <Badge tone="rose">Out</Badge>
                  ) : row.is_low_stock ? (
                    <Badge tone="amber">Low</Badge>
                  ) : (
                    <Badge tone="green">OK</Badge>
                  )}
                </div>
                <p className="text-xs text-slate-500">
                  {row.medicine_code} · {row.branch_name}
                </p>
                <p className="text-sm">
                  On hand <strong>{formatQty(row.qty_on_hand)}</strong> · reorder{" "}
                  {formatQty(row.reorder_level)}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

function LedgerTab() {
  const [entryType, setEntryType] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(search);

  const params = new URLSearchParams({ page_size: "25", page: String(page) });
  if (entryType) params.set("entry_type", entryType);
  if (debouncedSearch) params.set("search", debouncedSearch);

  const { data, isLoading, error } = useQuery({
    queryKey: ["inventory-ledger", entryType, debouncedSearch, page],
    queryFn: () =>
      api.get<Paginated<InventoryTransaction>>(`/inventory/transactions/?${params.toString()}`),
  });

  return (
    <Card>
      <CardHeader
        title="Stock ledger"
        subtitle={data ? `${data.count} movement(s)` : undefined}
        action={
          <div className="flex gap-2">
            <Input
              placeholder="Search medicine, batch, source…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-52"
            />
            <Select
              value={entryType}
              onChange={(e) => {
                setEntryType(e.target.value);
                setPage(1);
              }}
              className="w-40"
            >
              <option value="">All types</option>
              {ENTRY_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </Select>
          </div>
        }
      />
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : !data || data.results.length === 0 ? (
        <EmptyState message="No movements found." />
      ) : (
        <>
          <ul className="divide-y divide-slate-100">
            {data.results.map((txn) => {
              const positive = !txn.qty_delta.startsWith("-");
              return (
                <li
                  key={txn.id}
                  className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
                >
                  <div>
                    <p className="text-sm">
                      <span className="font-medium">{txn.medicine_name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">
                        {txn.medicine_code} / {txn.batch_number}
                      </span>
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatDate(txn.business_date)} · {txn.branch_name} ·{" "}
                      {txn.source_type || "manual"}
                      {txn.source_number ? ` #${txn.source_number}` : ""} ·{" "}
                      {txn.actor_name || "system"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge
                      tone={
                        txn.pool === "SALEABLE" ? "slate" : txn.pool === "PROMO" ? "blue" : "amber"
                      }
                    >
                      {txn.entry_type}
                    </Badge>
                    <span
                      className={`font-mono text-sm font-semibold ${positive ? "text-primary-700" : "text-danger-700"}`}
                    >
                      {positive ? "+" : ""}
                      {formatQty(txn.qty_delta)}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
          <Pagination
            page={page}
            hasPrevious={Boolean(data.previous)}
            hasNext={Boolean(data.next)}
            onChange={setPage}
          />
        </>
      )}
    </Card>
  );
}

function ExpiryList({
  title,
  endpoint,
  emptyMessage,
  daysParam,
}: {
  title: string;
  endpoint: string;
  emptyMessage: string;
  daysParam?: string;
}) {
  const params = daysParam ? `?days=${daysParam}` : "";
  const { data, isLoading, error } = useQuery({
    queryKey: ["report", endpoint, daysParam],
    queryFn: () => api.get<{ count: number; results: ExpiryReportRow[] }>(`${endpoint}${params}`),
  });

  return (
    <Card>
      <CardHeader title={title} subtitle={data ? `${data.count} batch(es)` : undefined} />
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : !data || data.results.length === 0 ? (
        <EmptyState message={emptyMessage} />
      ) : (
        <ul className="divide-y divide-slate-100">
          {data.results.slice(0, 12).map((row) => (
            <li
              key={`${row.medicine_code}-${row.batch_number}`}
              className="flex items-center justify-between px-4 py-2 text-sm"
            >
              <div>
                <p className="font-medium">{row.medicine_name}</p>
                <p className="text-xs text-slate-500">
                  {row.medicine_code} · batch {row.batch_number} · {row.branch_name}
                </p>
              </div>
              <div className="text-right">
                <p className={row.days_to_expiry < 0 ? "text-danger-700" : "text-amber-700"}>
                  {formatDate(row.expiry_date)} ({row.days_to_expiry}d)
                </p>
                <p className="text-xs text-slate-500">
                  qty {formatQty(row.qty_on_hand)} · value {formatMoney(row.value_on_hand)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function AlertsTab() {
  return (
    <div className="space-y-4">
      <ExpiryList
        title="Low stock"
        endpoint="/inventory/reports/low-stock/"
        emptyMessage="No medicines at or below reorder level."
      />
      <ExpiryList
        title="Near expiry (≤ 90 days)"
        endpoint="/inventory/reports/near-expiry/"
        emptyMessage="No batches approaching expiry."
      />
      <ExpiryList
        title="Expired stock"
        endpoint="/inventory/reports/expired/"
        emptyMessage="No expired batches with stock."
      />
    </div>
  );
}

function InventoryContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const rawTab = searchParams.get("tab");
  const tab: Tab = TABS.includes(rawTab as Tab) ? (rawTab as Tab) : "Stock";

  const setTab = (next: Tab) => {
    const params = new URLSearchParams(searchParams.toString());
    if (next === "Stock") params.delete("tab");
    else params.set("tab", next);
    const qs = params.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  };

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-800">Inventory</h1>

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "Stock" ? <StockTab /> : null}
      {tab === "Ledger" ? <LedgerTab /> : null}
      {tab === "Alerts" ? <AlertsTab /> : null}
    </div>
  );
}

export default function InventoryPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <InventoryContent />
    </Suspense>
  );
}
