"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge, Card, CardHeader, ErrorBanner, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import type { DashboardSummary, DashboardWidgets } from "@/lib/types";

function KpiCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800">{value}</p>
      {hint ? <p className="text-xs text-slate-500">{hint}</p> : null}
    </Card>
  );
}

function SalesTrend({ widgets }: { widgets: DashboardWidgets }) {
  const maxRevenue = Math.max(...widgets.sales_trend.map((row) => Number(row.revenue)), 1);
  return (
    <Card>
      <CardHeader
        title="Sales trend"
        subtitle={`Last ${widgets.period.days} days · ${widgets.sales_trend.reduce((sum, row) => sum + row.invoices, 0)} invoice(s)`}
      />
      {widgets.sales_trend.length === 0 ? (
        <p className="p-4 text-sm text-slate-500">No confirmed sales in this period.</p>
      ) : (
        <div className="flex h-32 items-end gap-1 px-4 pb-2 pt-4">
          {widgets.sales_trend.map((row) => (
            <div
              key={row.date}
              title={`${row.date}: ${formatMoney(row.revenue)} (${row.invoices})`}
              className="flex-1 rounded-t bg-primary-500/80 hover:bg-primary-600"
              style={{ height: `${Math.max((Number(row.revenue) / maxRevenue) * 100, 4)}%` }}
            />
          ))}
        </div>
      )}
      <div className="flex justify-between px-4 pb-3 text-xs text-slate-500">
        <span>{widgets.sales_trend[0]?.date ? formatDate(widgets.sales_trend[0].date) : ""}</span>
        <span>
          {widgets.sales_trend[widgets.sales_trend.length - 1]?.date
            ? formatDate(widgets.sales_trend[widgets.sales_trend.length - 1].date)
            : ""}
        </span>
      </div>
    </Card>
  );
}

function WidgetsSection() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-widgets"],
    queryFn: () => api.get<DashboardWidgets>("/dashboard/widgets/"),
  });

  if (isLoading) return <Spinner label="Loading widgets…" />;
  if (!data) return <ErrorBanner error={error} />;

  return (
    <div className="space-y-4">
      <ErrorBanner error={error} />
      <SalesTrend widgets={data} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Top items (period)" />
          {data.top_items.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">No sales yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.top_items.map((row) => (
                <li key={row.medicine} className="flex items-center justify-between px-4 py-2 text-sm">
                  <div>
                    <p className="font-medium">{row.name}</p>
                    <p className="text-xs text-slate-500">
                      {row.code} · qty {row.qty}
                    </p>
                  </div>
                  <span className="font-mono font-semibold">{formatMoney(row.revenue)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Top customers (period)" />
          {data.top_customers.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">No sales yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.top_customers.map((row) => (
                <li key={row.customer} className="flex items-center justify-between px-4 py-2 text-sm">
                  <div>
                    <p className="font-medium">{row.name}</p>
                    <p className="text-xs text-slate-500">{row.invoices} invoice(s)</p>
                  </div>
                  <span className="font-mono font-semibold">{formatMoney(row.revenue)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Low stock"
            subtitle="At or below reorder level"
            action={
              <Link href="/inventory" className="text-xs font-medium text-primary-700 hover:underline">
                Open inventory →
              </Link>
            }
          />
          {data.low_stock.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">No medicines at reorder level.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.low_stock.map((row) => (
                <li key={`${row.medicine}-${row.code}`} className="flex items-center justify-between px-4 py-2 text-sm">
                  <div>
                    <p className="font-medium">{row.name}</p>
                    <p className="text-xs text-slate-500">{row.code}</p>
                  </div>
                  <Badge tone="amber">
                    {row.on_hand} / reorder {row.reorder_level}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Near expiry (≤ 90 days)"
            action={
              <Link href="/inventory" className="text-xs font-medium text-primary-700 hover:underline">
                Open inventory →
              </Link>
            }
          />
          {data.near_expiry.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">No batches approaching expiry.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.near_expiry.map((row) => (
                <li
                  key={`${row.medicine}-${row.batch_number}`}
                  className="flex items-center justify-between px-4 py-2 text-sm"
                >
                  <div>
                    <p className="font-medium">{row.medicine}</p>
                    <p className="text-xs text-slate-500">
                      batch {row.batch_number} · qty {row.qty_on_hand}
                    </p>
                  </div>
                  <Badge tone={row.days_to_expiry <= 30 ? "rose" : "amber"}>
                    {formatDate(row.expiry_date)} ({row.days_to_expiry}d)
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary/"),
  });

  if (isLoading) return <Spinner label="Loading dashboard…" />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Dashboard</h1>
        {data ? (
          <span className="text-xs text-slate-500">
            {data.branch_scope === "ALL" ? "All branches" : "Assigned branches"} ·{" "}
            {formatDateTime(data.generated_at)}
          </span>
        ) : null}
      </div>

      <ErrorBanner error={error} />

      {data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard
              label="Medicines"
              value={String(data.medicines.active)}
              hint={`${data.medicines.total} total`}
            />
            <KpiCard
              label="Users"
              value={String(data.users.active)}
              hint={`${data.users.total} total`}
            />
            <KpiCard
              label="Branches"
              value={String(data.branches.active)}
              hint={`${data.branches.total} total`}
            />
            <KpiCard label="Roles" value={String(data.roles.total)} hint="RBAC roles" />
          </div>

          <Card>
            <CardHeader title="Operations" subtitle="Live figures from the ledgers." />
            <div className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
              {(
                [
                  ["Sales today", data.operations.sales_today, true],
                  ["Collections today", data.operations.collections_today, true],
                  ["Customer due", data.operations.customer_due, true],
                  ["Supplier payable", data.operations.supplier_payable, true],
                  ["Cash position", data.operations.cash_position, true],
                  ["Stock value", data.operations.stock_value, true],
                  ["Low stock", data.operations.low_stock_count, false],
                  ["Near expiry", data.operations.near_expiry_count, false],
                ] as Array<[string, string | number | null, boolean]>
              ).map(([label, value, isMoney]) => (
                <div key={label} className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xs text-slate-500">{label}</p>
                  <p className="text-lg font-semibold text-slate-700">
                    {isMoney ? formatMoney(value) : value === null ? "—" : String(value)}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          <WidgetsSection />
        </>
      ) : null}
    </div>
  );
}
