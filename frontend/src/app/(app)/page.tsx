"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Card, CardHeader, ErrorBanner, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import type {
  CollectionEfficiencyReport,
  DashboardSummary,
  DashboardWidgets,
  RepPerformanceReport,
  Representative,
} from "@/lib/types";

function KpiCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "danger" | "success" | "warning";
}) {
  const valueTone =
    tone === "danger"
      ? "text-danger-700"
      : tone === "success"
        ? "text-primary-700"
        : tone === "warning"
          ? "text-amber-600"
          : "text-slate-800";
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${valueTone}`}>{value}</p>
      {hint ? <p className="text-xs text-slate-500">{hint}</p> : null}
    </Card>
  );
}

const DAY_PRESETS = [7, 30, 60, 90] as const;

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

function CollectionEfficiencyKpi() {
  const { data, error } = useQuery({
    queryKey: ["collection-efficiency-kpi"],
    queryFn: () => api.get<CollectionEfficiencyReport>("/reports/collection-efficiency/"),
  });
  if (error) return null;
  if (!data) return null;
  const pct = data.kpi.collection_efficiency_pct;
  return (
    <KpiCard
      label="Collection efficiency (MTD)"
      value={`${pct}%`}
      hint={`${formatMoney(data.kpi.total_collected)} of ${formatMoney(data.kpi.total_invoiced)} due`}
      tone={pct >= 80 ? "success" : pct >= 50 ? "warning" : "danger"}
    />
  );
}

/**
 * Personal target-vs-actual card, shown only when the signed-in user is
 * linked to a representative record.
 */
function MyPerformanceCard() {
  const { user } = useAuth();
  const now = new Date();
  const fiscalYear = now.getFullYear();
  const periodMonth = now.getMonth() + 1;

  const repQuery = useQuery({
    queryKey: ["my-rep", user?.id],
    queryFn: () => api.get<Representative>("/representatives/me/"),
    enabled: Boolean(user?.id),
    retry: false,
  });
  const rep = repQuery.data;

  const perfQuery = useQuery({
    queryKey: ["rep-performance", rep?.id, fiscalYear, periodMonth],
    queryFn: () =>
      api.get<RepPerformanceReport>(
        `/reports/rep-performance/?representative=${rep?.id}&fiscal_year=${fiscalYear}&period_month=${periodMonth}`,
      ),
    enabled: Boolean(rep),
  });

  if (!rep) return null;
  const row = perfQuery.data?.results[0];
  const pct = row?.achievement_pct ?? null;

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            My target this month
          </p>
          {perfQuery.isLoading ? (
            <p className="mt-1 text-sm text-slate-500">Loading…</p>
          ) : !row ? (
            <p className="mt-1 text-sm text-slate-500">No target set for this month.</p>
          ) : (
            <p className="mt-1 text-2xl font-bold text-slate-800">
              {formatMoney(row.actual_sales)}{" "}
              <span className="text-sm font-normal text-slate-500">
                of {formatMoney(row.target_amount)}
              </span>
            </p>
          )}
        </div>
        {pct !== null ? (
          <Badge tone={pct >= 100 ? "green" : pct >= 75 ? "amber" : "rose"}>{pct}% achieved</Badge>
        ) : null}
      </div>
      {row ? (
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full ${
              pct === null
                ? "bg-slate-300"
                : pct >= 100
                  ? "bg-primary-600"
                  : pct >= 75
                    ? "bg-amber-500"
                    : "bg-danger-500"
            }`}
            style={{ width: `${Math.min(pct ?? 0, 100)}%` }}
          />
        </div>
      ) : null}
    </Card>
  );
}

function WidgetsSection({ days }: { days: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-widgets", days],
    queryFn: () => api.get<DashboardWidgets>(`/dashboard/widgets/?days=${days}`),
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
                <li
                  key={row.medicine}
                  className="flex items-center justify-between px-4 py-2 text-sm"
                >
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
                <li
                  key={row.customer}
                  className="flex items-center justify-between px-4 py-2 text-sm"
                >
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
              <Link
                href="/inventory"
                className="text-xs font-medium text-primary-700 hover:underline"
              >
                Open inventory →
              </Link>
            }
          />
          {data.low_stock.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">No medicines at reorder level.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.low_stock.map((row) => (
                <li
                  key={`${row.medicine}-${row.code}`}
                  className="flex items-center justify-between px-4 py-2 text-sm"
                >
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
              <Link
                href="/inventory"
                className="text-xs font-medium text-primary-700 hover:underline"
              >
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
  const [days, setDays] = useState<number>(30);
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
          {/* Rep-specific personal performance (when linked) */}
          <MyPerformanceCard />

          {/* Financial KPIs first — the numbers a business runs on */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <KpiCard label="Sales today" value={formatMoney(data.operations.sales_today)} />
            <KpiCard
              label="Collections today"
              value={formatMoney(data.operations.collections_today)}
            />
            <KpiCard
              label="Customer due"
              value={formatMoney(data.operations.customer_due)}
              tone="danger"
            />
            <KpiCard
              label="Supplier payable"
              value={formatMoney(data.operations.supplier_payable)}
              tone="warning"
            />
            <CollectionEfficiencyKpi />
          </div>

          {/* Secondary operational strip */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <KpiCard label="Cash position" value={formatMoney(data.operations.cash_position)} />
            <KpiCard label="Stock value" value={formatMoney(data.operations.stock_value)} />
            <KpiCard
              label="Low stock items"
              value={
                data.operations.low_stock_count === null
                  ? "—"
                  : String(data.operations.low_stock_count)
              }
              hint="At or below reorder level"
            />
            <KpiCard
              label="Near expiry"
              value={
                data.operations.near_expiry_count === null
                  ? "—"
                  : String(data.operations.near_expiry_count)
              }
              hint="Batches expiring ≤ 90 days"
            />
            <Card className="p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">System</p>
              <p className="mt-1 text-sm text-slate-700">
                {data.medicines.active} medicines · {data.users.active} users ·{" "}
                {data.branches.active} branches
              </p>
              <p className="text-xs text-slate-500">Medicines/Users/Branches/Roles</p>
            </Card>
          </div>

          {/* Trend period selector */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-slate-700">Operations window</p>
            <div className="flex gap-1">
              {DAY_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setDays(preset)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                    days === preset
                      ? "bg-primary-600 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {preset}d
                </button>
              ))}
            </div>
          </div>

          <WidgetsSection days={days} />
        </>
      ) : null}
    </div>
  );
}
