"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type {
  AttributionReport,
  FinancialPositionReport,
  InventoryValuationReport,
  ProfitLossReport,
} from "@/lib/types";

const TABS = ["Profit & Loss", "Inventory valuation", "Position", "Sales by doctor", "Sales by rep"] as const;
type Tab = (typeof TABS)[number];

function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function deltaTone(value: string | null): "green" | "rose" | "slate" {
  if (value === null) return "slate";
  return Number(value) >= 0 ? "green" : "rose";
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
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
      <Card className="p-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="From">
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </Field>
        </div>
      </Card>

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
              <p className="text-xl font-bold text-emerald-700">{money(data.current.gross_profit)}</p>
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
              <p className="text-xl font-bold text-rose-700">{money(data.current.losses.total)}</p>
              <p className="text-xs text-slate-500">
                Damage {money(data.current.losses.damage)} · expiry {money(data.current.losses.expiry)}
              </p>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Comparison vs previous period"
              subtitle={`Same length ending ${data.previous.period.date_to}`}
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
      ) : null}
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
      <Card className="p-4">
        <p className="text-xs uppercase text-slate-500">Total inventory value (batch cost)</p>
        <p className="text-2xl font-bold text-slate-800">{money(data?.total_value)}</p>
      </Card>
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
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Receivables (customer dues)</p>
              <p className="text-xl font-bold text-rose-700">{money(data.receivables)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Payables (supplier dues)</p>
              <p className="text-xl font-bold text-amber-700">{money(data.payables)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs uppercase text-slate-500">Cash & bank</p>
              <p className="text-xl font-bold text-emerald-700">{money(data.cash_position)}</p>
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

function AttributionTab({ endpoint, label }: { endpoint: string; label: string }) {
  const [dateFrom, setDateFrom] = useState(monthStartIso());
  const [dateTo, setDateTo] = useState(todayIso());

  const { data, isLoading, error } = useQuery({
    queryKey: ["attribution", endpoint, dateFrom, dateTo],
    queryFn: () => api.get<AttributionReport>(`${endpoint}?date_from=${dateFrom}&date_to=${dateTo}`),
  });

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="From">
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </Field>
        </div>
      </Card>
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

export default function ReportsPage() {
  const [tab, setTab] = useState<Tab>("Profit & Loss");

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-800">Reports</h1>
      <div className="flex flex-wrap gap-2">
        {TABS.map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
              tab === item ? "bg-emerald-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {tab === "Profit & Loss" ? <ProfitLossTab /> : null}
      {tab === "Inventory valuation" ? <ValuationTab /> : null}
      {tab === "Position" ? <PositionTab /> : null}
      {tab === "Sales by doctor" ? <AttributionTab endpoint="/reports/sales-by-doctor/" label="Sales by doctor" /> : null}
      {tab === "Sales by rep" ? <AttributionTab endpoint="/reports/sales-by-rep/" label="Sales by representative" /> : null}
    </div>
  );
}
