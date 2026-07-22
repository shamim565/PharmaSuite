"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Branch, FinancialAccount, Income, IncomeCategory, Paginated } from "@/lib/types";

const emptyForm = {
  branch: "",
  category: "",
  amount: "",
  account: "",
  source: "",
  reference: "",
  note: "",
};

export default function IncomePage() {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const params = new URLSearchParams({ page_size: "50" });
  if (search) params.set("search", search);
  if (status) params.set("status", status);

  const incomesQuery = useQuery({
    queryKey: ["incomes", search, status],
    queryFn: () => api.get<Paginated<Income>>(`/incomes/?${params.toString()}`),
  });
  const summaryQuery = useQuery({
    queryKey: ["income-summary"],
    queryFn: () =>
      api.get<{ count: number; total: string; results: { category_name: string; total: string }[] }>(
        "/incomes/reports/summary/",
      ),
  });
  const categoriesQuery = useQuery({
    queryKey: ["income-categories"],
    queryFn: () => api.get<Paginated<IncomeCategory>>("/income-categories/?page_size=100&is_active=true"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });
  const accountsQuery = useQuery({
    queryKey: ["accounts", "select"],
    queryFn: () => api.get<Paginated<FinancialAccount>>("/accounts/?page_size=50&is_active=true"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["incomes"] });
    queryClient.invalidateQueries({ queryKey: ["income-summary"] });
    queryClient.invalidateQueries({ queryKey: ["accounts"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) => api.post<Income>("/incomes/", payload),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      invalidate();
    },
  });
  const reverseMutation = useMutation({
    mutationFn: (income: Income) => api.post(`/incomes/${income.id}/reverse/`, { reason: "reversed from register" }),
    onSuccess: () => invalidate(),
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate(form);
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Other income</h1>
        <div className="flex flex-wrap gap-2">
          <Input placeholder="Search source, voucher…" value={search} onChange={(e) => setSearch(e.target.value)} className="w-48" />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-32">
            <option value="">All statuses</option>
            <option value="POSTED">Posted</option>
            <option value="REVERSED">Reversed</option>
          </Select>
          {hasPerm("INCOME_POST") ? (
            <Button size="sm" onClick={() => setShowForm((v) => !v)}>
              {showForm ? "Close" : "New income"}
            </Button>
          ) : null}
        </div>
      </div>

      {summaryQuery.data ? (
        <Card className="p-4">
          <p className="text-xs uppercase text-slate-500">Posted income</p>
          <p className="text-2xl font-bold text-emerald-700">{summaryQuery.data.total}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {summaryQuery.data.results.map((row) => (
              <span key={row.category_name} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                {row.category_name}: <strong>{row.total}</strong>
              </span>
            ))}
          </div>
        </Card>
      ) : null}

      {showForm && hasPerm("INCOME_POST") ? (
        <Card>
          <CardHeader title="New income" subtitle="Commission, service income, scrap sales, etc." />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error} />
            </div>
            <Field label="Branch" error={fieldError("branch")}>
              <Select value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })} required>
                <option value="">Select…</option>
                {branchesQuery.data?.results.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Category" error={fieldError("category")}>
              <Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} required>
                <option value="">Select…</option>
                {categoriesQuery.data?.results.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Amount" error={fieldError("amount")}>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                required
              />
            </Field>
            <Field label="Received in" error={fieldError("account")}>
              <Select value={form.account} onChange={(e) => setForm({ ...form, account: e.target.value })} required>
                <option value="">Select…</option>
                {accountsQuery.data?.results.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name} ({account.balance_cache})
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Source / payer" error={fieldError("source")}>
              <Input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} />
            </Field>
            <Field label="Reference" error={fieldError("reference")}>
              <Input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
            </Field>
            <div className="col-span-2">
              <Field label="Note" error={fieldError("note")}>
                <Input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
              </Field>
            </div>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Record income"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Income register" subtitle={incomesQuery.data ? `${incomesQuery.data.count} entry(ies)` : undefined} />
        <ErrorBanner error={incomesQuery.error} />
        {incomesQuery.isLoading ? (
          <Spinner />
        ) : !incomesQuery.data || incomesQuery.data.results.length === 0 ? (
          <EmptyState message="No income recorded yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {incomesQuery.data.results.map((income) => (
              <li key={income.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    {income.number}{" "}
                    <span className="text-xs text-slate-400">{income.category_name}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {income.business_date} · {income.account_name} · {income.source || "—"}
                    {income.posted_by_name ? ` · by ${income.posted_by_name}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-semibold">{income.amount}</span>
                  {income.status === "POSTED" ? <Badge tone="green">Posted</Badge> : <Badge tone="rose">Reversed</Badge>}
                  {income.status === "POSTED" && hasPerm("INCOME_POST") ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => reverseMutation.mutate(income)}
                      disabled={reverseMutation.isPending}
                    >
                      Reverse
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
