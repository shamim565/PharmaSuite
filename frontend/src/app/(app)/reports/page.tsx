"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import type { ReactNode } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Pagination, Spinner, Tabs } from "@/components/ui";
import { api, apiDownload } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import type {
  AttributionReport,
  ExpiryReportRow,
  FinancialPositionReport,
  InventoryTransaction,
  InventoryValuationReport,
  Paginated,
  PayableAgingRow,
  ProfitLossReport,
  PurchasesSummaryReport,
  ReceivableAgingRow,
  SalesByCustomerReport,
  SalesByItemReport,
  SalesSummaryReport,
  VisitCoverageRow,
} from "@/lib/types";

const TABS = [
  "Profit & Loss",
  "Sales summary",
  "Sales by item",
  "Sales by customer",
  "Purchases",
  "Inventory valuation",
  "Position",
  "Aging",
  "Expiry",
  "Stock movement",
  "Sales by doctor",
  "Sales by rep",
  "Visit coverage",
] as const;
type Tab = (typeof TABS)[number];

const TAB_SLUGS: Record<Tab, string> = {
  "Profit & Loss": "pl",
  "Sales summary": "sales-summary",
  "Sales by item": "by-item",
  "Sales by customer": "by-customer",
  Purchases: "purchases",
  "Inventory valuation": "valuation",
  Position: "position",
  Aging: "aging",
  Expiry: "expiry",
  "Stock movement": "movement",
  "Sales by doctor": "by-doctor",
  "Sales by rep": "by-rep",
  "Visit coverage": "visits",
};
const SLUG_TO_TAB = Object.fromEntries(
  Object.entries(TAB_SLUGS).map(([tab, slug]) => [slug, tab]),
) as Record<string, Tab>;

function isoDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

type PresetKey = "today" | "7d" | "month" | "lastMonth" | "fy";

const PRESET_OPTIONS: Array<{ key: PresetKey; label: string }> = [
  { key: "today", label: "Today" },
  { key: "7d", label: "Last 7 days" },
  { key: "month", label: "This month" },
  { key: "lastMonth", label: "Last month" },
  { key: "fy", label: "This FY" },
];

function presetRange(preset: PresetKey): [string, string] {
  const now = new Date();
  const today = isoDate(now);
  switch (preset) {
    case "today":
      return [today, today];
    case "7d": {
      const start = new Date(now);
      start.setDate(start.getDate() - 6);
      return [isoDate(start), today];
    }
    case "month":
      return [`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`, today];
    case "lastMonth": {
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const end = new Date(now.getFullYear(), now.getMonth(), 0);
      return [isoDate(start), isoDate(end)];
    }
    case "fy": {
      // Fiscal year runs July–June.
      const startYear = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
      return [`${startYear}-07-01`, today];
    }
  }
}

function DateRangeFilterCard({
  dateFrom,
  dateTo,
  setDateFrom,
  setDateTo,
  children,
}: {
  dateFrom: string;
  dateTo: string;
  setDateFrom: (value: string) => void;
  setDateTo: (value: string) => void;
  children?: ReactNode;
}) {
  return (
    <Card className="no-print p-4">
      <div className="mb-3 flex flex-wrap items-center gap-1">
        {PRESET_OPTIONS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => {
              const [from, to] = presetRange(key);
              setDateFrom(from);
              setDateTo(to);
            }}
            className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-200"
          >
            {label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Field label="From">
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </Field>
        <Field label="To">
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </Field>
        {children}
      </div>
    </Card>
  );
}

function MiniBarChart({
  rows,
  tone = "primary",
}: {
  rows: Array<{ label: string; value: string; hint: string }>;
  tone?: "primary" | "sky";
}) {
  const max = Math.max(...rows.map((row) => Number(row.value)), 1);
  return (
    <>
      <div className="flex h-40 items-end gap-0.5 px-4 pt-4">
        {rows.map((row) => (
          <div
            key={row.label}
            title={row.hint}
            className={`flex-1 rounded-t ${
              tone === "primary" ? "bg-primary-500/80 hover:bg-primary-600" : "bg-sky-500/70 hover:bg-sky-600"
            }`}
            style={{ height: `${Math.max((Number(row.value) / max) * 100, 3)}%` }}
          />
        ))}
      </div>
      <div className="flex justify-between px-4 pb-3 text-xs text-slate-500">
        <span>{formatDate(rows[0]?.label)}</span>
        <span>{formatDate(rows[rows.length - 1]?.label)}</span>
      </div>
    </>
  );
}

function money(value: string | number | null | undefined): string {
  return formatMoney(value);
}

function deltaTone(value: string | null): "green" | "rose" | "slate" {
  if (value === null) return "slate";
  return Number(value) >= 0 ? "green" : "rose";
}

function todayIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function monthStartIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function ProfitLossTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const { data, isLoading, error } = useQuery({
    queryKey: ["pl-report", dateFrom, dateTo],
    queryFn: () => api.get<ProfitLossReport>(`/reports/profit-loss/?date_from=${dateFrom}&date_to=${dateTo}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      >
        <Button
          size="sm"
          variant="secondary"
          className="self-end"
          onClick={() => apiDownload(`/reports/profit-loss/?date_from=${dateFrom}&date_to=${dateTo}&export=csv`, "profit-loss.csv")}
        >
          Download CSV
        </Button>
      </DateRangeFilterCard>

      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner label="Computing P&L…" />
      ) : data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Net revenue</p>
              <p className="text-xl font-bold text-slate-800">{money(data.current.revenue.net_revenue)}</p>
              <p className="text-xs text-slate-500">
                Sales {money(data.current.revenue.sales_net)} − returns {money(data.current.revenue.returns_net)}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Gross profit</p>
              <p className="text-xl font-bold text-primary-700">{money(data.current.gross_profit)}</p>
              <p className="text-xs text-slate-500">
                COGS {money(data.current.cogs)}
                {data.current.gross_margin_pct ? ` · margin ${data.current.gross_margin_pct}%` : ""}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Net profit</p>
              <p className="text-xl font-bold text-slate-800">{money(data.current.net_profit)}</p>
              <p className="text-xs text-slate-500">
                Expenses {money(data.current.expenses)} · income {money(data.current.other_income)}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Losses</p>
              <p className="text-xl font-bold text-danger-700">{money(data.current.losses.total)}</p>
              <p className="text-xs text-slate-500">
                Damage {money(data.current.losses.damage)} · expiry {money(data.current.losses.expiry)}
              </p>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Comparison vs previous period"
              subtitle={`Same length ending ${data.previous.period.date_to ? formatDate(data.previous.period.date_to) : "—"}`}
            />
            <div className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
              <div>
                <p className="text-xs text-slate-500">Revenue change</p>
                <p className="text-lg font-semibold">
                  {money(data.comparison.revenue_delta)}{" "}
                  <Badge tone={deltaTone(data.comparison.revenue_delta)}>
                    {data.comparison.revenue_delta_pct ? `${data.comparison.revenue_delta_pct}%` : "—"}
                  </Badge>
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Previous revenue</p>
                <p className="text-lg font-semibold text-slate-600">{money(data.previous.revenue.net_revenue)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Net profit change</p>
                <p className="text-lg font-semibold">
                  {money(data.comparison.net_profit_delta)}{" "}
                  <Badge tone={deltaTone(data.comparison.net_profit_delta)}>
                    {data.comparison.net_profit_delta_pct ? `${data.comparison.net_profit_delta_pct}%` : "—"}
                  </Badge>
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Previous net profit</p>
                <p className="text-lg font-semibold text-slate-600">{money(data.previous.net_profit)}</p>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Reconciliation" subtitle={data.current.reconciliation.note} />
            <div className="grid grid-cols-2 gap-3 p-4 text-sm">
              <div>
                <p className="text-xs text-slate-500">Customer ledger movement (period)</p>
                <p className="font-semibold">{money(data.current.reconciliation.customer_ledger_delta)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Receipts (period)</p>
                <p className="font-semibold">{money(data.current.reconciliation.receipts)}</p>
              </div>
            </div>
          </Card>
        </>
      ) : (
        <EmptyState message="No data for this period." />
      )}
    </div>
  );
}

function ValuationTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["valuation-report"],
    queryFn: () => api.get<InventoryValuationReport>("/reports/inventory-valuation/"),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <Card className="p-4">
          <p className="text-xs uppercase text-slate-500">Total inventory value (batch cost)</p>
          <p className="text-2xl font-bold text-slate-800">{money(data?.total_value)}</p>
        </Card>
        <Button size="sm" variant="secondary" onClick={() => apiDownload("/reports/inventory-valuation/?export=csv", "inventory-valuation.csv")}>
          Download CSV
        </Button>
      </div>
      <Card>
        <CardHeader title="Valuation by branch" subtitle={data ? `${data.count} branch(es)` : undefined} />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No stock." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Branch</th>
                  <th className="px-4 py-2 text-right">Saleable qty</th>
                  <th className="px-4 py-2 text-right">Saleable value</th>
                  <th className="px-4 py-2 text-right">Quarantine</th>
                  <th className="px-4 py-2 text-right">Promo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.branch}>
                    <td className="px-4 py-2 font-medium">{row.branch_name}</td>
                    <td className="px-4 py-2 text-right">{row.saleable_qty}</td>
                    <td className="px-4 py-2 text-right">{money(row.saleable_value)}</td>
                    <td className="px-4 py-2 text-right">{money(row.quarantine_value)}</td>
                    <td className="px-4 py-2 text-right">{money(row.promo_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function PositionTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["position-report"],
    queryFn: () => api.get<FinancialPositionReport>("/reports/financial-position/"),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" variant="secondary" onClick={() => apiDownload("/reports/financial-position/?export=csv", "financial-position.csv")}>
          Download CSV
        </Button>
      </div>
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Receivables (customer dues)</p>
              <p className="text-xl font-bold text-danger-700">{money(data.receivables)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Payables (supplier dues)</p>
              <p className="text-xl font-bold text-amber-700">{money(data.payables)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Cash & bank</p>
              <p className="text-xl font-bold text-primary-700">{money(data.cash_position)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Stock value (saleable)</p>
              <p className="text-xl font-bold text-slate-800">{money(data.stock_value_saleable)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Quarantine value</p>
              <p className="text-xl font-bold text-slate-600">{money(data.stock_value_quarantine)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Net working position</p>
              <p className="text-xl font-bold text-slate-800">{money(data.net_working_position)}</p>
            </Card>
          </div>

          <Card>
            <CardHeader title="Account balances" />
            <ul className="divide-y divide-slate-100">
              {data.accounts.map((account) => (
                <li key={account.account} className="flex items-center justify-between px-4 py-2 text-sm">
                  <div>
                    <p className="font-medium">{account.name}</p>
                    <p className="text-xs text-slate-500">
                      {account.code} · {account.account_type}
                    </p>
                  </div>
                  <span className="font-mono font-semibold">{money(account.balance)}</span>
                </li>
              ))}
            </ul>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function VisitCoverageTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const { data, isLoading, error } = useQuery({
    queryKey: ["visit-coverage", dateFrom, dateTo],
    queryFn: () =>
      api.get<{
        count: number;
        ad_hoc_completed: number;
        results: VisitCoverageRow[];
      }>(`/doctors/reports/visit-coverage/?date_from=${dateFrom}&date_to=${dateTo}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      />
      <Card>
        <CardHeader
          title="Visit coverage by representative"
          subtitle={
            data
              ? `${data.count} rep(s) · ${data.ad_hoc_completed} ad-hoc visit(s) completed outside plans`
              : undefined
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No visits in this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Representative</th>
                  <th className="px-4 py-2 text-right">Planned</th>
                  <th className="px-4 py-2 text-right">Completed</th>
                  <th className="px-4 py-2 text-right">Missed</th>
                  <th className="px-4 py-2 text-right">Cancelled</th>
                  <th className="px-4 py-2 text-right">Coverage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.representative}>
                    <td className="px-4 py-2 font-medium">{row.representative_name}</td>
                    <td className="px-4 py-2 text-right">{row.planned}</td>
                    <td className="px-4 py-2 text-right text-primary-700">{row.completed}</td>
                    <td className="px-4 py-2 text-right text-danger-700">{row.missed}</td>
                    <td className="px-4 py-2 text-right text-slate-500">{row.cancelled}</td>
                    <td className="px-4 py-2 text-right">
                      {row.coverage_pct === null ? (
                        "—"
                      ) : (
                        <Badge tone={row.coverage_pct >= 80 ? "green" : row.coverage_pct >= 50 ? "amber" : "rose"}>
                          {row.coverage_pct}%
                        </Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function AttributionTab({ endpoint, label }: { endpoint: string; label: string }) {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const { data, isLoading, error } = useQuery({
    queryKey: ["attribution", endpoint, dateFrom, dateTo],
    queryFn: () => api.get<AttributionReport>(`${endpoint}?date_from=${dateFrom}&date_to=${dateTo}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      >
        <Button
          size="sm"
          variant="secondary"
          className="self-end"
          onClick={() => apiDownload(`${endpoint}?date_from=${dateFrom}&date_to=${dateTo}&export=csv`, "attribution.csv")}
        >
          Download CSV
        </Button>
      </DateRangeFilterCard>
      <Card>
        <CardHeader
          title={label}
          subtitle={data ? `Total net revenue ${money(data.total_net_revenue)} across ${data.count} group(s)` : undefined}
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No attributed sales in this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2 text-right">Invoices</th>
                  <th className="px-4 py-2 text-right">Net revenue</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={`${row.id}-${row.name}`}>
                    <td className="px-4 py-2 font-medium">{row.name}</td>
                    <td className="px-4 py-2 text-right">{row.invoice_count}</td>
                    <td className="px-4 py-2 text-right">{money(row.net_revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function SalesSummaryTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const { data, isLoading, error } = useQuery({
    queryKey: ["sales-summary", dateFrom, dateTo],
    queryFn: () => api.get<SalesSummaryReport>(`/reports/sales-summary/?date_from=${dateFrom}&date_to=${dateTo}`),
  });
  const purchasesQuery = useQuery({
    queryKey: ["purchases-summary", dateFrom, dateTo],
    queryFn: () => api.get<PurchasesSummaryReport>(`/reports/purchases-summary/?date_from=${dateFrom}&date_to=${dateTo}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      >
        <Button
          size="sm"
          variant="secondary"
          className="self-end"
          onClick={() => apiDownload(`/reports/sales-summary/?date_from=${dateFrom}&date_to=${dateTo}&export=csv`, "sales-summary.csv")}
        >
          Download sales CSV
        </Button>
        <Button
          size="sm"
          variant="secondary"
          className="self-end"
          onClick={() => apiDownload(`/reports/purchases-summary/?date_from=${dateFrom}&date_to=${dateTo}&export=csv`, "purchases-summary.csv")}
        >
          Download purchases CSV
        </Button>
      </DateRangeFilterCard>

      <ErrorBanner error={error ?? purchasesQuery.error} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Daily sales"
            subtitle={data ? `Net ${money(data.totals.net_revenue)} · VAT ${money(data.totals.vat)} · Grand ${money(data.totals.grand_total)}` : undefined}
          />
          {isLoading ? (
            <Spinner />
          ) : !data || data.results.length === 0 ? (
            <EmptyState message="No sales in this period." />
          ) : (
            <MiniBarChart
              rows={data.results.map((row) => ({
                label: row.date,
                value: row.net_revenue,
                hint: `${formatDate(row.date)}: ${money(row.net_revenue)} · ${row.invoices} invoice(s) · VAT ${money(row.vat)}`,
              }))}
            />
          )}
        </Card>

        <Card>
          <CardHeader
            title="Daily purchases"
            subtitle={purchasesQuery.data ? `Net cost ${money(purchasesQuery.data.totals.net_cost)}` : undefined}
          />
          {purchasesQuery.isLoading ? (
            <Spinner />
          ) : !purchasesQuery.data || purchasesQuery.data.results.length === 0 ? (
            <EmptyState message="No purchases in this period." />
          ) : (
            <MiniBarChart
              tone="sky"
              rows={purchasesQuery.data.results.map((row) => ({
                label: row.date,
                value: row.net_cost,
                hint: `${formatDate(row.date)}: ${money(row.net_cost)} · ${row.purchases} purchase(s) · VAT ${money(row.vat)}`,
              }))}
            />
          )}
        </Card>
      </div>
    </div>
  );
}

function ItemsReportTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());
  const [search, setSearch] = useState("");

  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (search) params.set("search", search);
  const { data, isLoading, error } = useQuery({
    queryKey: ["sales-by-item", dateFrom, dateTo, search],
    queryFn: () => api.get<SalesByItemReport>(`/reports/sales-by-item/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      >
        <Field label="Search medicine">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="name contains…" />
        </Field>
        <Button
          size="sm"
          variant="secondary"
          className="self-end"
          onClick={() => apiDownload(`/reports/sales-by-item/?${params.toString()}&export=csv`, "sales-by-item.csv")}
        >
          Download CSV
        </Button>
      </DateRangeFilterCard>

      <Card>
        <CardHeader title="Sales by item" subtitle={data ? `${data.count} item(s)` : undefined} />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No item sales in this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Medicine</th>
                  <th className="px-4 py-2 text-right">Qty</th>
                  <th className="px-4 py-2 text-right">Gross</th>
                  <th className="px-4 py-2 text-right">Discount</th>
                  <th className="px-4 py-2 text-right">Net</th>
                  {data.has_cost_access ? <th className="px-4 py-2 text-right">Cost</th> : null}
                  {data.has_cost_access ? <th className="px-4 py-2 text-right">Profit</th> : null}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.medicine}>
                    <td className="px-4 py-2">
                      <span className="font-medium">{row.name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">{row.code}</span>
                    </td>
                    <td className="px-4 py-2 text-right">{row.qty}</td>
                    <td className="px-4 py-2 text-right">{money(row.gross)}</td>
                    <td className="px-4 py-2 text-right">{money(row.discount)}</td>
                    <td className="px-4 py-2 text-right font-medium">{money(row.net_revenue)}</td>
                    {data.has_cost_access ? (
                      <td className="px-4 py-2 text-right">{row.cost ? money(row.cost) : "—"}</td>
                    ) : null}
                    {data.has_cost_access ? (
                      <td className="px-4 py-2 text-right font-medium text-primary-700">
                        {row.gross_profit !== null && row.gross_profit !== undefined ? money(row.gross_profit) : "—"}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function CustomersReportTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());
  const [search, setSearch] = useState("");

  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (search) params.set("search", search);
  const { data, isLoading, error } = useQuery({
    queryKey: ["sales-by-customer", dateFrom, dateTo, search],
    queryFn: () => api.get<SalesByCustomerReport>(`/reports/sales-by-customer/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      >
        <Field label="Search customer">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} />
        </Field>
        <Button
          size="sm"
          variant="secondary"
          className="self-end"
          onClick={() => apiDownload(`/reports/sales-by-customer/?${params.toString()}&export=csv`, "sales-by-customer.csv")}
        >
          Download CSV
        </Button>
      </DateRangeFilterCard>

      <Card>
        <CardHeader title="Sales by customer" subtitle={data ? `${data.count} customer(s)` : undefined} />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No customer sales in this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Customer</th>
                  <th className="px-4 py-2 text-right">Invoices</th>
                  <th className="px-4 py-2 text-right">Net revenue</th>
                  <th className="px-4 py-2 text-right">Paid</th>
                  <th className="px-4 py-2 text-right">Outstanding</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.customer}>
                    <td className="px-4 py-2">
                      <span className="font-medium">{row.name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">{row.code}</span>
                    </td>
                    <td className="px-4 py-2 text-right">{row.invoices}</td>
                    <td className="px-4 py-2 text-right font-medium">{money(row.net_revenue)}</td>
                    <td className="px-4 py-2 text-right">{money(row.paid)}</td>
                    <td className="px-4 py-2 text-right text-danger-700">{money(row.outstanding)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function PurchasesTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const { data, isLoading, error } = useQuery({
    queryKey: ["purchases-summary", dateFrom, dateTo],
    queryFn: () => api.get<PurchasesSummaryReport>(`/reports/purchases-summary/?date_from=${dateFrom}&date_to=${dateTo}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      >
        <Button
          size="sm"
          variant="secondary"
          className="self-end"
          onClick={() =>
            apiDownload(
              `/reports/purchases-summary/?date_from=${dateFrom}&date_to=${dateTo}&export=csv`,
              "purchases-summary.csv",
            )
          }
        >
          Download CSV
        </Button>
      </DateRangeFilterCard>
      <Card>
        <CardHeader
          title="Daily purchases"
          subtitle={data ? `Net cost ${money(data.totals.net_cost)} · ${data.totals.purchases} purchase(s)` : undefined}
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No purchases in this period." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.results.map((row) => (
              <li key={row.date} className="flex items-center justify-between px-4 py-2 text-sm">
                <div>
                  <p className="font-medium">{formatDate(row.date)}</p>
                  <p className="text-xs text-slate-500">
                    {row.purchases} purchase(s) · VAT {money(row.vat)}
                  </p>
                </div>
                <span className="font-mono font-semibold">{money(row.net_cost)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function AgingTab() {
  const receivables = useQuery({
    queryKey: ["receivable-aging"],
    queryFn: () =>
      api.get<{ count: number; totals: Record<string, string>; results: ReceivableAgingRow[] }>(
        "/sales/reports/receivable-aging/",
      ),
  });
  const payables = useQuery({
    queryKey: ["payable-aging"],
    queryFn: () =>
      api.get<{ count: number; totals: Record<string, string>; results: PayableAgingRow[] }>(
        "/purchases/reports/payable-aging/",
      ),
  });

  const BUCKETS: Array<[string, string]> = [
    ["current", "Current"],
    ["days_1_30", "1–30 days"],
    ["days_31_60", "31–60"],
    ["days_61_90", "61–90"],
    ["days_90_plus", "90+"],
  ];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Receivables aging (customers)"
          subtitle={receivables.data ? `Total outstanding ${money(receivables.data.totals.total)} across ${receivables.data.count} customer(s)` : undefined}
        />
        <ErrorBanner error={receivables.error} />
        {receivables.isLoading ? (
          <Spinner />
        ) : !receivables.data || receivables.data.results.length === 0 ? (
          <EmptyState message="No outstanding receivables." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Customer</th>
                  {BUCKETS.map(([key, label]) => (
                    <th key={key} className="px-4 py-2 text-right">{label}</th>
                  ))}
                  <th className="px-4 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {receivables.data.results.map((row) => (
                  <tr key={row.customer}>
                    <td className="px-4 py-2">
                      <span className="font-medium">{row.customer_name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">{row.customer_code}</span>
                    </td>
                    {BUCKETS.map(([key]) => (
                      <td key={key} className="px-4 py-2 text-right">
                        {Number(row[key as keyof ReceivableAgingRow]) > 0
                          ? money(row[key as keyof ReceivableAgingRow] as string)
                          : "—"}
                      </td>
                    ))}
                    <td className="px-4 py-2 text-right font-semibold">{money(row.total)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-slate-200 bg-slate-50 text-sm font-semibold">
                <tr>
                  <td className="px-4 py-2">Totals</td>
                  {BUCKETS.map(([key]) => (
                    <td key={key} className="px-4 py-2 text-right">{money(receivables.data?.totals[key])}</td>
                  ))}
                  <td className="px-4 py-2 text-right">{money(receivables.data?.totals.total)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Payables aging (suppliers)"
          subtitle={payables.data ? `Total payable ${money(payables.data.totals.total)} across ${payables.data.count} supplier(s)` : undefined}
        />
        <ErrorBanner error={payables.error} />
        {payables.isLoading ? (
          <Spinner />
        ) : !payables.data || payables.data.results.length === 0 ? (
          <EmptyState message="No outstanding payables." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Supplier</th>
                  {BUCKETS.map(([key, label]) => (
                    <th key={key} className="px-4 py-2 text-right">{label}</th>
                  ))}
                  <th className="px-4 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {payables.data.results.map((row) => (
                  <tr key={row.supplier}>
                    <td className="px-4 py-2">
                      <span className="font-medium">{row.supplier_name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">{row.supplier_code}</span>
                    </td>
                    {BUCKETS.map(([key]) => (
                      <td key={key} className="px-4 py-2 text-right">
                        {Number(row[key as keyof PayableAgingRow]) > 0
                          ? money(row[key as keyof PayableAgingRow] as string)
                          : "—"}
                      </td>
                    ))}
                    <td className="px-4 py-2 text-right font-semibold">{money(row.total)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-slate-200 bg-slate-50 text-sm font-semibold">
                <tr>
                  <td className="px-4 py-2">Totals</td>
                  {BUCKETS.map(([key]) => (
                    <td key={key} className="px-4 py-2 text-right">{money(payables.data?.totals[key])}</td>
                  ))}
                  <td className="px-4 py-2 text-right">{money(payables.data?.totals.total)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function ExpiryReportTab() {
  const nearExpiry = useQuery({
    queryKey: ["report", "near-expiry", "90"],
    queryFn: () => api.get<{ count: number; results: ExpiryReportRow[] }>("/inventory/reports/near-expiry/?days=90"),
  });
  const expired = useQuery({
    queryKey: ["report", "expired"],
    queryFn: () => api.get<{ count: number; results: ExpiryReportRow[] }>("/inventory/reports/expired/"),
  });

  const expiryList = (
    data: { count: number; results: ExpiryReportRow[] } | undefined,
    isLoading: boolean,
    emptyMessage: string,
    highlight: "amber" | "danger",
  ) => {
    if (isLoading) return <Spinner />;
    if (!data || data.results.length === 0) return <EmptyState message={emptyMessage} />;
    return (
      <ul className="divide-y divide-slate-100">
        {data.results.map((row) => (
          <li
            key={`${row.medicine_code}-${row.batch_number}`}
            className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm"
          >
            <div>
              <p className="font-medium">{row.medicine_name}</p>
              <p className="text-xs text-slate-500">
                {row.medicine_code} · batch {row.batch_number} · {row.branch_name}
              </p>
            </div>
            <div className="text-right">
              <p className={highlight === "danger" ? "text-danger-700" : "text-amber-700"}>
                {formatDate(row.expiry_date)} ({row.days_to_expiry}d)
              </p>
              <p className="text-xs text-slate-500">
                qty {formatQty(row.qty_on_hand)} · value {money(row.value_on_hand)}
              </p>
            </div>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Near expiry (≤ 90 days)"
          subtitle={nearExpiry.data ? `${nearExpiry.data.count} batch(es)` : undefined}
        />
        <ErrorBanner error={nearExpiry.error} />
        {expiryList(nearExpiry.data, nearExpiry.isLoading, "No batches approaching expiry.", "amber")}
      </Card>
      <Card>
        <CardHeader
          title="Expired stock"
          subtitle={expired.data ? `${expired.data.count} batch(es)` : undefined}
        />
        <ErrorBanner error={expired.error} />
        {expiryList(expired.data, expired.isLoading, "No expired batches with stock.", "danger")}
      </Card>
    </div>
  );
}

function StockMovementTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());
  const [page, setPage] = useState(1);

  const params = new URLSearchParams({
    page_size: "50",
    page: String(page),
    date_from: dateFrom,
    date_to: dateTo,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["stock-movement", dateFrom, dateTo, page],
    queryFn: () => api.get<Paginated<InventoryTransaction>>(`/inventory/transactions/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={(value) => {
          setDateFrom(value);
          setPage(1);
        }}
        setDateTo={(value) => {
          setDateTo(value);
          setPage(1);
        }}
      />
      <Card>
        <CardHeader
          title="Stock movement"
          subtitle={data ? `${data.count} movement(s) in period` : undefined}
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No stock movements in this period." />
        ) : (
          <>
            <ul className="divide-y divide-slate-100">
              {data.results.map((txn) => {
                const positive = !txn.qty_delta.startsWith("-");
                return (
                  <li key={txn.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                    <div>
                      <p className="text-sm">
                        <span className="font-medium">{txn.medicine_name}</span>{" "}
                        <span className="font-mono text-xs text-slate-500">
                          {txn.medicine_code} / {txn.batch_number}
                        </span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatDate(txn.business_date)} · {txn.branch_name} · {txn.source_type || "manual"}
                        {txn.source_number ? ` #${txn.source_number}` : ""} · {txn.actor_name || "system"}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge tone={txn.pool === "SALEABLE" ? "slate" : txn.pool === "PROMO" ? "blue" : "amber"}>
                        {txn.entry_type}
                      </Badge>
                      <span className={`font-mono text-sm font-semibold ${positive ? "text-primary-700" : "text-danger-700"}`}>
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
    </div>
  );
}

function ReportsContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tab: Tab = SLUG_TO_TAB[searchParams.get("tab") ?? ""] ?? "Profit & Loss";

  const setTab = (next: Tab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", TAB_SLUGS[next]);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Reports</h1>
        <Button size="sm" variant="secondary" className="no-print" onClick={() => window.print()}>
          Print
        </Button>
      </div>
      <Tabs tabs={TABS} active={tab} onChange={setTab} className="no-print" />

      {tab === "Profit & Loss" ? <ProfitLossTab /> : null}
      {tab === "Sales summary" ? <SalesSummaryTab /> : null}
      {tab === "Sales by item" ? <ItemsReportTab /> : null}
      {tab === "Sales by customer" ? <CustomersReportTab /> : null}
      {tab === "Purchases" ? <PurchasesTab /> : null}
      {tab === "Inventory valuation" ? <ValuationTab /> : null}
      {tab === "Position" ? <PositionTab /> : null}
      {tab === "Aging" ? <AgingTab /> : null}
      {tab === "Expiry" ? <ExpiryReportTab /> : null}
      {tab === "Stock movement" ? <StockMovementTab /> : null}
      {tab === "Sales by doctor" ? <AttributionTab endpoint="/reports/sales-by-doctor/" label="Sales by doctor" /> : null}
      {tab === "Sales by rep" ? <AttributionTab endpoint="/reports/sales-by-rep/" label="Sales by representative" /> : null}
      {tab === "Visit coverage" ? <VisitCoverageTab /> : null}
    </div>
  );
}

export default function ReportsPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <ReportsContent />
    </Suspense>
  );
}
