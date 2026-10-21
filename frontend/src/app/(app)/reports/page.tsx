"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import type { ReactNode } from "react";

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
  Tabs,
} from "@/components/ui";
import { api, apiDownload } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type {
  AttributionReport,
  CollectionEfficiencyReport,
  ExceptionReport,
  ExpiryReportRow,
  FinancialPositionReport,
  InventoryDsiReport,
  InventoryTransaction,
  InventoryValuationReport,
  MarginAnalysisReport,
  Paginated,
  PayableAgingRow,
  ProfitLossReport,
  PurchasesSummaryReport,
  ReceivableAgingRow,
  RepPerformanceReport,
  SalesByCustomerReport,
  SalesByItemReport,
  SalesSummaryReport,
  SupplierConcentrationReport,
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
  "Inventory DSI",
  "Margin analysis",
  "Rep performance",
  "Collection efficiency",
  "Supplier concentration",
  "Exceptions",
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
  "Inventory DSI": "dsi",
  "Margin analysis": "margin",
  "Rep performance": "rep-perf",
  "Collection efficiency": "collection",
  "Supplier concentration": "concentration",
  Exceptions: "exceptions",
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
              tone === "primary"
                ? "bg-primary-500/80 hover:bg-primary-600"
                : "bg-sky-500/70 hover:bg-sky-600"
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
    queryFn: () =>
      api.get<ProfitLossReport>(`/reports/profit-loss/?date_from=${dateFrom}&date_to=${dateTo}`),
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
              `/reports/profit-loss/?date_from=${dateFrom}&date_to=${dateTo}&export=csv`,
              "profit-loss.csv",
            )
          }
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
              <p className="text-xl font-bold text-slate-800">
                {money(data.current.revenue.net_revenue)}
              </p>
              <p className="text-xs text-slate-500">
                Sales {money(data.current.revenue.sales_net)} − returns{" "}
                {money(data.current.revenue.returns_net)}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Gross profit</p>
              <p className="text-xl font-bold text-primary-700">
                {money(data.current.gross_profit)}
              </p>
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
              <p className="text-xl font-bold text-danger-700">
                {money(data.current.losses.total)}
              </p>
              <p className="text-xs text-slate-500">
                Damage {money(data.current.losses.damage)} · expiry{" "}
                {money(data.current.losses.expiry)}
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
                    {data.comparison.revenue_delta_pct
                      ? `${data.comparison.revenue_delta_pct}%`
                      : "—"}
                  </Badge>
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Previous revenue</p>
                <p className="text-lg font-semibold text-slate-600">
                  {money(data.previous.revenue.net_revenue)}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Net profit change</p>
                <p className="text-lg font-semibold">
                  {money(data.comparison.net_profit_delta)}{" "}
                  <Badge tone={deltaTone(data.comparison.net_profit_delta)}>
                    {data.comparison.net_profit_delta_pct
                      ? `${data.comparison.net_profit_delta_pct}%`
                      : "—"}
                  </Badge>
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Previous net profit</p>
                <p className="text-lg font-semibold text-slate-600">
                  {money(data.previous.net_profit)}
                </p>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Reconciliation" subtitle={data.current.reconciliation.note} />
            <div className="grid grid-cols-2 gap-3 p-4 text-sm">
              <div>
                <p className="text-xs text-slate-500">Customer ledger movement (period)</p>
                <p className="font-semibold">
                  {money(data.current.reconciliation.customer_ledger_delta)}
                </p>
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
        <Button
          size="sm"
          variant="secondary"
          onClick={() =>
            apiDownload("/reports/inventory-valuation/?export=csv", "inventory-valuation.csv")
          }
        >
          Download CSV
        </Button>
      </div>
      <Card>
        <CardHeader
          title="Valuation by branch"
          subtitle={data ? `${data.count} branch(es)` : undefined}
        />
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
        <Button
          size="sm"
          variant="secondary"
          onClick={() =>
            apiDownload("/reports/financial-position/?export=csv", "financial-position.csv")
          }
        >
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
              <p className="text-xl font-bold text-slate-600">
                {money(data.stock_value_quarantine)}
              </p>
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
                <li
                  key={account.account}
                  className="flex items-center justify-between px-4 py-2 text-sm"
                >
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
                        <Badge
                          tone={
                            row.coverage_pct >= 80
                              ? "green"
                              : row.coverage_pct >= 50
                                ? "amber"
                                : "rose"
                          }
                        >
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
    queryFn: () =>
      api.get<AttributionReport>(`${endpoint}?date_from=${dateFrom}&date_to=${dateTo}`),
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
              `${endpoint}?date_from=${dateFrom}&date_to=${dateTo}&export=csv`,
              "attribution.csv",
            )
          }
        >
          Download CSV
        </Button>
      </DateRangeFilterCard>
      <Card>
        <CardHeader
          title={label}
          subtitle={
            data
              ? `Total net revenue ${money(data.total_net_revenue)} across ${data.count} group(s)`
              : undefined
          }
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
    queryFn: () =>
      api.get<SalesSummaryReport>(
        `/reports/sales-summary/?date_from=${dateFrom}&date_to=${dateTo}`,
      ),
  });
  const purchasesQuery = useQuery({
    queryKey: ["purchases-summary", dateFrom, dateTo],
    queryFn: () =>
      api.get<PurchasesSummaryReport>(
        `/reports/purchases-summary/?date_from=${dateFrom}&date_to=${dateTo}`,
      ),
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
              `/reports/sales-summary/?date_from=${dateFrom}&date_to=${dateTo}&export=csv`,
              "sales-summary.csv",
            )
          }
        >
          Download sales CSV
        </Button>
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
          Download purchases CSV
        </Button>
      </DateRangeFilterCard>

      <ErrorBanner error={error ?? purchasesQuery.error} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Daily sales"
            subtitle={
              data
                ? `Net ${money(data.totals.net_revenue)} · VAT ${money(data.totals.vat)} · Grand ${money(data.totals.grand_total)}`
                : undefined
            }
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
            subtitle={
              purchasesQuery.data
                ? `Net cost ${money(purchasesQuery.data.totals.net_cost)}`
                : undefined
            }
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
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="name contains…"
          />
        </Field>
        <Button
          size="sm"
          variant="secondary"
          className="self-end"
          onClick={() =>
            apiDownload(
              `/reports/sales-by-item/?${params.toString()}&export=csv`,
              "sales-by-item.csv",
            )
          }
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
                        {row.gross_profit !== null && row.gross_profit !== undefined
                          ? money(row.gross_profit)
                          : "—"}
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
    queryFn: () =>
      api.get<SalesByCustomerReport>(`/reports/sales-by-customer/?${params.toString()}`),
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
          onClick={() =>
            apiDownload(
              `/reports/sales-by-customer/?${params.toString()}&export=csv`,
              "sales-by-customer.csv",
            )
          }
        >
          Download CSV
        </Button>
      </DateRangeFilterCard>

      <Card>
        <CardHeader
          title="Sales by customer"
          subtitle={data ? `${data.count} customer(s)` : undefined}
        />
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
                    <td className="px-4 py-2 text-right text-danger-700">
                      {money(row.outstanding)}
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

function PurchasesTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const { data, isLoading, error } = useQuery({
    queryKey: ["purchases-summary", dateFrom, dateTo],
    queryFn: () =>
      api.get<PurchasesSummaryReport>(
        `/reports/purchases-summary/?date_from=${dateFrom}&date_to=${dateTo}`,
      ),
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
          subtitle={
            data
              ? `Net cost ${money(data.totals.net_cost)} · ${data.totals.purchases} purchase(s)`
              : undefined
          }
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
          subtitle={
            receivables.data
              ? `Total outstanding ${money(receivables.data.totals.total)} across ${receivables.data.count} customer(s)`
              : undefined
          }
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
                    <th key={key} className="px-4 py-2 text-right">
                      {label}
                    </th>
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
                    <td key={key} className="px-4 py-2 text-right">
                      {money(receivables.data?.totals[key])}
                    </td>
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
          subtitle={
            payables.data
              ? `Total payable ${money(payables.data.totals.total)} across ${payables.data.count} supplier(s)`
              : undefined
          }
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
                    <th key={key} className="px-4 py-2 text-right">
                      {label}
                    </th>
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
                    <td key={key} className="px-4 py-2 text-right">
                      {money(payables.data?.totals[key])}
                    </td>
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
    queryFn: () =>
      api.get<{ count: number; results: ExpiryReportRow[] }>(
        "/inventory/reports/near-expiry/?days=90",
      ),
  });
  const expired = useQuery({
    queryKey: ["report", "expired"],
    queryFn: () =>
      api.get<{ count: number; results: ExpiryReportRow[] }>("/inventory/reports/expired/"),
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
        {expiryList(
          nearExpiry.data,
          nearExpiry.isLoading,
          "No batches approaching expiry.",
          "amber",
        )}
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
    queryFn: () =>
      api.get<Paginated<InventoryTransaction>>(`/inventory/transactions/?${params.toString()}`),
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
                          txn.pool === "SALEABLE"
                            ? "slate"
                            : txn.pool === "PROMO"
                              ? "blue"
                              : "amber"
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
    </div>
  );
}

/* ─────────────────────────── BI: Inventory DSI ─────────────────────── */

function InventoryDsiTab() {
  const [filterType, setFilterType] = useState("all"); // all | dead | slow
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);

  const params = new URLSearchParams();
  if (filterType !== "all") params.set("filter", filterType);
  if (debouncedSearch) params.set("search", debouncedSearch);

  const { data, isLoading, error } = useQuery({
    queryKey: ["report", "dsi", filterType, debouncedSearch],
    queryFn: () => api.get<InventoryDsiReport>(`/reports/inventory-dsi/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Inventory DSI & dead stock"
          subtitle={
            data
              ? `Avg sales window ${data.period_days} days · dead > ${data.dead_days_threshold} days without sale · slow > ${data.slow_dsi_threshold} DSI`
              : undefined
          }
          action={
            <div className="flex flex-wrap gap-2">
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm"
                aria-label="Filter DSI rows"
              >
                <option value="all">All stock</option>
                <option value="dead">Dead stock only</option>
                <option value="slow">Slow movers only</option>
              </select>
              <Input
                placeholder="Search medicine…"
                aria-label="Search medicines"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-48"
              />
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  apiDownload(
                    `/reports/inventory-dsi/?${params.toString()}&export=csv`,
                    "inventory-dsi.csv",
                  )
                }
              >
                CSV
              </Button>
            </div>
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No stock with on-hand quantity." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Medicine</th>
                  <th className="px-4 py-2 text-right">On hand</th>
                  <th className="px-4 py-2 text-right">Avg daily sales</th>
                  <th className="px-4 py-2 text-right">DSI (days)</th>
                  <th className="px-4 py-2 text-right">Last sale</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.medicine}>
                    <td className="px-4 py-2">
                      <span className="font-medium">{row.name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">{row.code}</span>
                    </td>
                    <td className="px-4 py-2 text-right">{formatQty(row.qty_on_hand)}</td>
                    <td className="px-4 py-2 text-right">{formatQty(row.avg_daily_sales)}</td>
                    <td className="px-4 py-2 text-right">{row.dsi === null ? "—" : row.dsi}</td>
                    <td className="px-4 py-2 text-right">
                      {row.days_since_sale === null ? "never" : `${row.days_since_sale}d`}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {row.is_dead_stock ? <Badge tone="rose">Dead</Badge> : null}
                        {row.is_slow_mover ? <Badge tone="amber">Slow</Badge> : null}
                        {!row.is_dead_stock && !row.is_slow_mover ? (
                          <Badge tone="green">Healthy</Badge>
                        ) : null}
                      </div>
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

/* ─────────────────────────── BI: Margin analysis ───────────────────── */

function MarginAnalysisTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());
  const [groupBy, setGroupBy] = useState("category");

  const params = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
    group_by: groupBy,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["report", "margin", dateFrom, dateTo, groupBy],
    queryFn: () => api.get<MarginAnalysisReport>(`/reports/margin-analysis/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      >
        <Field label="Group by">
          <Select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="category">Medicine category</option>
            <option value="generic">Generic</option>
          </Select>
        </Field>
        <div className="flex items-end">
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              apiDownload(
                `/reports/margin-analysis/?${params.toString()}&export=csv`,
                `margin-by-${groupBy}.csv`,
              )
            }
          >
            CSV
          </Button>
        </div>
      </DateRangeFilterCard>
      <Card>
        <CardHeader
          title={`Margin by ${groupBy === "generic" ? "generic" : "category"}`}
          subtitle={
            data
              ? `Net revenue ${money(data.total_net_revenue)}${
                  data.total_gross_profit !== null
                    ? ` · gross profit ${money(data.total_gross_profit)}`
                    : ""
                }`
              : undefined
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No sales in this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">{groupBy === "generic" ? "Generic" : "Category"}</th>
                  <th className="px-4 py-2 text-right">Qty</th>
                  <th className="px-4 py-2 text-right">Gross</th>
                  <th className="px-4 py-2 text-right">Discount</th>
                  <th className="px-4 py-2 text-right">Net revenue</th>
                  {data.has_cost_access ? (
                    <>
                      <th className="px-4 py-2 text-right">COGS</th>
                      <th className="px-4 py-2 text-right">Gross profit</th>
                      <th className="px-4 py-2 text-right">Margin %</th>
                    </>
                  ) : null}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.id || row.name}>
                    <td className="px-4 py-2 font-medium">{row.name}</td>
                    <td className="px-4 py-2 text-right">{formatQty(row.qty)}</td>
                    <td className="px-4 py-2 text-right">{money(row.gross)}</td>
                    <td className="px-4 py-2 text-right">{money(row.discount)}</td>
                    <td className="px-4 py-2 text-right">{money(row.net_revenue)}</td>
                    {data.has_cost_access ? (
                      <>
                        <td className="px-4 py-2 text-right">{money(row.cogs)}</td>
                        <td className="px-4 py-2 text-right">{money(row.gross_profit)}</td>
                        <td className="px-4 py-2 text-right">
                          <Badge
                            tone={
                              (row.gross_profit_pct ?? 0) < 0
                                ? "rose"
                                : (row.gross_profit_pct ?? 0) < 10
                                  ? "amber"
                                  : "green"
                            }
                          >
                            {row.gross_profit_pct?.toFixed(1)}%
                          </Badge>
                        </td>
                      </>
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

/* ─────────────────────────── BI: Rep performance ───────────────────── */

function RepPerformanceTab() {
  const now = new Date();
  const [fiscalYear, setFiscalYear] = useState(now.getFullYear());
  const [periodMonth, setPeriodMonth] = useState(now.getMonth() + 1);

  const params = new URLSearchParams({
    fiscal_year: String(fiscalYear),
    period_month: String(periodMonth),
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["report", "rep-performance", fiscalYear, periodMonth],
    queryFn: () => api.get<RepPerformanceReport>(`/reports/rep-performance/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <Card className="no-print p-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="Fiscal year">
            <Input
              type="number"
              min={2000}
              max={2100}
              value={fiscalYear}
              onChange={(e) => setFiscalYear(Number(e.target.value) || now.getFullYear())}
            />
          </Field>
          <Field label="Month">
            <Select value={periodMonth} onChange={(e) => setPeriodMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  {new Date(2020, i, 1).toLocaleDateString("en-GB", { month: "long" })}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex items-end">
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                apiDownload(
                  `/reports/rep-performance/?${params.toString()}&export=csv`,
                  "rep-performance.csv",
                )
              }
            >
              CSV
            </Button>
          </div>
        </div>
      </Card>
      <Card>
        <CardHeader
          title="Rep performance — target vs actual"
          subtitle={
            data
              ? `Actual ${money(data.total_actual)} vs target ${money(data.total_target)} · ${data.count} rep(s)`
              : undefined
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No reps with targets or sales in this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Rep</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2 text-right">Target</th>
                  <th className="px-4 py-2 text-right">Actual</th>
                  <th className="px-4 py-2 text-right">Gap</th>
                  <th className="px-4 py-2">Achievement</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.representative}>
                    <td className="px-4 py-2">
                      <span className="font-medium">{row.name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">{row.code}</span>
                      <span className="block text-xs text-slate-500">{row.branch_name}</span>
                    </td>
                    <td className="px-4 py-2 text-xs">{row.rep_type}</td>
                    <td className="px-4 py-2 text-right">{money(row.target_amount)}</td>
                    <td className="px-4 py-2 text-right">{money(row.actual_sales)}</td>
                    <td
                      className={`px-4 py-2 text-right ${
                        Number(row.gap) > 0 ? "text-danger-700" : "text-primary-700"
                      }`}
                    >
                      {Number(row.gap) > 0 ? "-" : "+"}
                      {money(Math.abs(Number(row.gap)))}
                    </td>
                    <td className="px-4 py-2">
                      {row.achievement_pct === null ? (
                        <Badge tone="slate">No target</Badge>
                      ) : (
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className={`h-full rounded-full ${
                                row.achievement_pct >= 100
                                  ? "bg-primary-600"
                                  : row.achievement_pct >= 75
                                    ? "bg-amber-500"
                                    : "bg-danger-500"
                              }`}
                              style={{ width: `${Math.min(row.achievement_pct, 100)}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium">{row.achievement_pct}%</span>
                        </div>
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

/* ──────────────────────── BI: Collection efficiency ────────────────── */

function CollectionEfficiencyTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });

  const { data, isLoading, error } = useQuery({
    queryKey: ["report", "collection-efficiency", dateFrom, dateTo],
    queryFn: () =>
      api.get<CollectionEfficiencyReport>(`/reports/collection-efficiency/?${params.toString()}`),
  });

  const kpi = data?.kpi;

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      />
      {kpi ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Card className="p-4">
            <p className="text-xs text-slate-500">Invoiced (due in period)</p>
            <p className="text-lg font-semibold">{money(kpi.total_invoiced)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-slate-500">Collected</p>
            <p className="text-lg font-semibold">{money(kpi.total_collected)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-slate-500">Outstanding</p>
            <p className="text-lg font-semibold text-danger-700">{money(kpi.total_outstanding)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-slate-500">Collection efficiency</p>
            <p
              className={`text-lg font-semibold ${
                kpi.collection_efficiency_pct >= 80
                  ? "text-primary-700"
                  : kpi.collection_efficiency_pct >= 50
                    ? "text-amber-600"
                    : "text-danger-700"
              }`}
            >
              {kpi.collection_efficiency_pct}%
            </p>
          </Card>
        </div>
      ) : null}
      <Card>
        <CardHeader
          title="Collection efficiency by customer"
          subtitle={data ? `${data.count} customer(s)` : undefined}
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                apiDownload(
                  `/reports/collection-efficiency/?${params.toString()}&export=csv`,
                  "collection-efficiency.csv",
                )
              }
            >
              CSV
            </Button>
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No invoices due in this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Customer</th>
                  <th className="px-4 py-2 text-right">Invoiced</th>
                  <th className="px-4 py-2 text-right">Collected</th>
                  <th className="px-4 py-2 text-right">Outstanding</th>
                  <th className="px-4 py-2">Efficiency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.customer}>
                    <td className="px-4 py-2">
                      <span className="font-medium">{row.name}</span>{" "}
                      <span className="font-mono text-xs text-slate-500">{row.code}</span>
                    </td>
                    <td className="px-4 py-2 text-right">{money(row.invoiced)}</td>
                    <td className="px-4 py-2 text-right">{money(row.collected)}</td>
                    <td className="px-4 py-2 text-right">{money(row.outstanding)}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${
                              row.efficiency_pct >= 80
                                ? "bg-primary-600"
                                : row.efficiency_pct >= 50
                                  ? "bg-amber-500"
                                  : "bg-danger-500"
                            }`}
                            style={{ width: `${Math.min(row.efficiency_pct, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium">{row.efficiency_pct}%</span>
                      </div>
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

/* ─────────────────────── BI: Supplier concentration ────────────────── */

function SupplierConcentrationTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });

  const { data, isLoading, error } = useQuery({
    queryKey: ["report", "supplier-concentration", dateFrom, dateTo],
    queryFn: () =>
      api.get<SupplierConcentrationReport>(`/reports/supplier-concentration/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      />
      {data ? (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <Card className="p-4">
            <p className="text-xs text-slate-500">Total purchase spend</p>
            <p className="text-lg font-semibold">{money(data.total_spend)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-slate-500">Suppliers</p>
            <p className="text-lg font-semibold">{data.supplier_count}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-slate-500">High dependency (≥30%)</p>
            <p
              className={`text-lg font-semibold ${data.high_dependency_count > 0 ? "text-danger-700" : "text-primary-700"}`}
            >
              {data.high_dependency_count}
            </p>
          </Card>
        </div>
      ) : null}
      <Card>
        <CardHeader
          title="Purchase concentration by supplier"
          subtitle="Share of confirmed purchases in the period"
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                apiDownload(
                  `/reports/supplier-concentration/?${params.toString()}&export=csv`,
                  "supplier-concentration.csv",
                )
              }
            >
              CSV
            </Button>
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No confirmed purchases in this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Supplier</th>
                  <th className="px-4 py-2 text-right">Purchases</th>
                  <th className="px-4 py-2 text-right">Spend</th>
                  <th className="px-4 py-2 text-right">Share %</th>
                  <th className="px-4 py-2 text-right">Cumulative %</th>
                  <th className="px-4 py-2">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((row) => (
                  <tr key={row.supplier}>
                    <td className="px-4 py-2 font-medium">{row.name}</td>
                    <td className="px-4 py-2 text-right">{row.purchase_count}</td>
                    <td className="px-4 py-2 text-right">{money(row.total_spend)}</td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${row.high_dependency ? "bg-danger-500" : "bg-primary-500"}`}
                            style={{ width: `${Math.min(row.pct_of_total, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium">{row.pct_of_total}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-slate-500">
                      {row.cumulative_pct}%
                    </td>
                    <td className="px-4 py-2">
                      {row.high_dependency ? <Badge tone="rose">High dependency</Badge> : null}
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

/* ─────────────────────────── BI: Exceptions ────────────────────────── */

const OVERRIDE_LABELS: Record<string, string> = {
  CREDIT_OVERRIDE: "Credit limit",
  FEFO_OVERRIDE: "FEFO batch",
  RX_OVERRIDE: "Rx bypass",
  PRICE_OVERRIDE: "Price",
  ZERO_VALUE: "Zero value",
  BELOW_COST: "Below cost",
  DUPLICATE_INVOICE: "Duplicate invoice",
};

function ExceptionsTab() {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());
  const [overrideType, setOverrideType] = useState("");

  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (overrideType) params.set("override_type", overrideType);

  const { data, isLoading, error } = useQuery({
    queryKey: ["report", "exceptions", dateFrom, dateTo, overrideType],
    queryFn: () => api.get<ExceptionReport>(`/reports/exceptions/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <DateRangeFilterCard
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
      >
        <Field label="Override type">
          <Select value={overrideType} onChange={(e) => setOverrideType(e.target.value)}>
            <option value="">All overrides</option>
            <option value="CREDIT_OVERRIDE">Credit limit</option>
            <option value="FEFO_OVERRIDE">FEFO batch</option>
            <option value="RX_OVERRIDE">Rx bypass</option>
            <option value="ZERO_VALUE">Zero value</option>
            <option value="BELOW_COST">Below cost</option>
            <option value="DUPLICATE_INVOICE">Duplicate invoice</option>
          </Select>
        </Field>
        <div className="flex items-end">
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              apiDownload(`/reports/exceptions/?${params.toString()}&export=csv`, "exceptions.csv")
            }
          >
            CSV
          </Button>
        </div>
      </DateRangeFilterCard>
      <Card>
        <CardHeader
          title="Override & exception report"
          subtitle={
            data
              ? `${data.total_exceptions} exception(s) · ${data.invoice_exceptions} invoice / ${data.purchase_exceptions} purchase`
              : undefined
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No overrides in this period. Clean!" />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.results.map((row) => (
              <li key={`${row.document_type}-${row.document_id}`} className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium">
                      {row.document_number ?? "Draft"} ·{" "}
                      {row.customer_name ?? row.supplier_name ?? ""}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatDate(row.business_date)} ·{" "}
                      {row.document_type === "SALES_INVOICE" ? "Invoice" : "Purchase"} ·{" "}
                      {row.branch_name} · by {row.confirmed_by || "—"}
                    </p>
                  </div>
                  <span className="text-sm font-semibold">{money(row.grand_total)}</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {row.overrides.map((override) => (
                    <Badge key={override.type} tone="rose">
                      {OVERRIDE_LABELS[override.type] ?? override.type}
                      {override.reason ? `: ${override.reason}` : ""}
                    </Badge>
                  ))}
                </div>
              </li>
            ))}
          </ul>
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
      {tab === "Sales by doctor" ? (
        <AttributionTab endpoint="/reports/sales-by-doctor/" label="Sales by doctor" />
      ) : null}
      {tab === "Sales by rep" ? (
        <AttributionTab endpoint="/reports/sales-by-rep/" label="Sales by representative" />
      ) : null}
      {tab === "Visit coverage" ? <VisitCoverageTab /> : null}
      {tab === "Inventory DSI" ? <InventoryDsiTab /> : null}
      {tab === "Margin analysis" ? <MarginAnalysisTab /> : null}
      {tab === "Rep performance" ? <RepPerformanceTab /> : null}
      {tab === "Collection efficiency" ? <CollectionEfficiencyTab /> : null}
      {tab === "Supplier concentration" ? <SupplierConcentrationTab /> : null}
      {tab === "Exceptions" ? <ExceptionsTab /> : null}
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
