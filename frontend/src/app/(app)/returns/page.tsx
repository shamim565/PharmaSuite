"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Input, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { Paginated, Purchase, SalesReturn } from "@/lib/types";

const TABS = ["Sales returns", "Purchase returns"] as const;
type Tab = (typeof TABS)[number];

function reasonTone(reason: string): "slate" | "amber" | "rose" {
  if (reason === "DAMAGED" || reason === "EXPIRED" || reason === "EXPIRED_AT_CUSTOMER") return "rose";
  if (reason === "WRONG_ITEM" || reason === "OVER_SUPPLY") return "amber";
  return "slate";
}

export default function ReturnsPage() {
  const { hasPerm } = useAuth();
  const [tab, setTab] = useState<Tab>("Sales returns");
  const [search, setSearch] = useState("");

  const salesQuery = useQuery({
    queryKey: ["sales-returns", search],
    queryFn: () => api.get<Paginated<SalesReturn>>(`/sales-returns/?page_size=50&search=${encodeURIComponent(search)}`),
    enabled: tab === "Sales returns",
  });
  const purchaseQuery = useQuery({
    queryKey: ["purchase-returns", search],
    queryFn: () => api.get<Paginated<{ id: string; number: string; purchase_number: string; supplier_name: string; business_date: string; reason_code: string; status: string; grand_total: string }>>(
      `/purchase-returns/?page_size=50&search=${encodeURIComponent(search)}`,
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
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-56"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {visibleTabs.map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
              activeTab === item ? "bg-emerald-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {item}
          </button>
        ))}
      </div>

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
                        <span className="text-xs text-slate-400">
                          invoice{" "}
                          <Link href={`/sales/${salesReturn.invoice}`} className="text-emerald-700 hover:underline">
                            {salesReturn.invoice_number}
                          </Link>
                        </span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {salesReturn.customer_name} · {salesReturn.business_date} ·{" "}
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
                      <span className="font-mono font-semibold">{salesReturn.grand_total}</span>
                    </div>
                  </div>
                  {salesReturn.items.some((item) => !item.restocked) ? (
                    <p className="text-xs text-amber-700">Some lines went to quarantine (damaged/expired).</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
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
                      <span className="text-xs text-slate-400">purchase {purchaseReturn.purchase_number}</span>
                    </p>
                    <p className="text-xs text-slate-500">
                      {purchaseReturn.supplier_name} · {purchaseReturn.business_date}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={reasonTone(purchaseReturn.reason_code)}>
                      {purchaseReturn.reason_code.replace(/_/g, " ")}
                    </Badge>
                    <Badge tone={purchaseReturn.status === "CONFIRMED" ? "green" : "slate"}>
                      {purchaseReturn.status}
                    </Badge>
                    <span className="font-mono font-semibold">{purchaseReturn.grand_total}</span>
                    <Link href="/purchases">
                      <Button size="sm" variant="secondary">
                        Open purchases
                      </Button>
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}
    </div>
  );
}
