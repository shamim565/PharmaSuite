"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Branch, Expense, ExpenseCategory, FinancialAccount, Paginated } from "@/lib/types";

const emptyForm = {
  branch: "",
  category: "",
  amount: "",
  account: "",
  payee: "",
  reference: "",
  note: "",
};

function statusTone(status: Expense["status"]): "green" | "amber" | "rose" | "slate" {
  if (status === "POSTED") return "green";
  if (status === "PENDING_APPROVAL") return "amber";
  if (status === "REJECTED" || status === "REVERSED") return "rose";
  return "slate";
}

export default function ExpensesPage() {
  const queryClient = useQueryClient();
  const { user, hasPerm } = useAuth();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [rejectFor, setRejectFor] = useState<Expense | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const params = new URLSearchParams({ page_size: "50" });
  if (status) params.set("status", status);
  if (search) params.set("search", search);

  const expensesQuery = useQuery({
    queryKey: ["expenses", status, search],
    queryFn: () => api.get<Paginated<Expense>>(`/expenses/?${params.toString()}`),
  });
  const summaryQuery = useQuery({
    queryKey: ["expense-summary"],
    queryFn: () =>
      api.get<{ count: number; total: string; results: { category_name: string; total: string; count: number }[] }>(
        "/expenses/reports/summary/",
      ),
  });
  const categoriesQuery = useQuery({
    queryKey: ["expense-categories"],
    queryFn: () => api.get<Paginated<ExpenseCategory>>("/expense-categories/?page_size=100&is_active=true"),
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
    queryClient.invalidateQueries({ queryKey: ["expenses"] });
    queryClient.invalidateQueries({ queryKey: ["expense-summary"] });
    queryClient.invalidateQueries({ queryKey: ["accounts"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) => api.post<Expense>("/expenses/", payload),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      invalidate();
    },
  });
  const actionMutation = useMutation({
    mutationFn: ({ id, action, reason }: { id: string; action: string; reason?: string }) =>
      api.post(`/expenses/${id}/${action}/`, reason ? { reason } : {}),
    onSuccess: () => {
      setRejectFor(null);
      setRejectReason("");
      invalidate();
    },
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
        <h1 className="text-lg font-semibold text-slate-800">Expenses</h1>
        <div className="flex flex-wrap gap-2">
          <Input placeholder="Search payee, voucher…" value={search} onChange={(e) => setSearch(e.target.value)} className="w-48" />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-36">
            <option value="">All statuses</option>
            <option value="POSTED">Posted</option>
            <option value="PENDING_APPROVAL">Pending</option>
            <option value="REJECTED">Rejected</option>
            <option value="REVERSED">Reversed</option>
          </Select>
          {hasPerm("EXPENSE_POST") ? (
            <Button size="sm" onClick={() => setShowForm((v) => !v)}>
              {showForm ? "Close" : "New expense"}
            </Button>
          ) : null}
        </div>
      </div>

      {summaryQuery.data ? (
        <Card className="p-4">
          <p className="text-xs uppercase text-slate-500">Posted expenses</p>
          <p className="text-2xl font-bold text-slate-800">{summaryQuery.data.total}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {summaryQuery.data.results.map((row) => (
              <span key={row.category_name} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                {row.category_name}: <strong>{row.total}</strong> ({row.count})
              </span>
            ))}
          </div>
        </Card>
      ) : null}

      {showForm && hasPerm("EXPENSE_POST") ? (
        <Card>
          <CardHeader title="New expense" subtitle="Above threshold expenses require approval." />
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
            <Field label="Paid from" error={fieldError("account")}>
              <Select value={form.account} onChange={(e) => setForm({ ...form, account: e.target.value })} required>
                <option value="">Select…</option>
                {accountsQuery.data?.results.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name} ({account.balance_cache})
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Payee" error={fieldError("payee")}>
              <Input value={form.payee} onChange={(e) => setForm({ ...form, payee: e.target.value })} />
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
                {createMutation.isPending ? "Saving…" : "Record expense"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      {rejectFor ? (
        <Card>
          <CardHeader
            title={`Reject expense ${rejectFor.number ?? ""}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setRejectFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={actionMutation.error} />
            <Field label="Reason">
              <Input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
            </Field>
            <Button
              variant="danger"
              disabled={actionMutation.isPending || !rejectReason}
              onClick={() => actionMutation.mutate({ id: rejectFor.id, action: "reject", reason: rejectReason })}
            >
              Reject expense
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Expense register" subtitle={expensesQuery.data ? `${expensesQuery.data.count} expense(s)` : undefined} />
        <ErrorBanner error={expensesQuery.error} />
        {expensesQuery.isLoading ? (
          <Spinner />
        ) : !expensesQuery.data || expensesQuery.data.results.length === 0 ? (
          <EmptyState message="No expenses yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {expensesQuery.data.results.map((expense) => {
              const canApprove =
                expense.status === "PENDING_APPROVAL" &&
                hasPerm("EXPENSE_APPROVE") &&
                expense.requested_by_name !== user?.full_name;
              return (
                <li key={expense.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                  <div>
                    <p className="font-medium">
                      {expense.number ?? "Pending"}{" "}
                      <span className="text-xs text-slate-400">{expense.category_name}</span>
                    </p>
                    <p className="text-xs text-slate-500">
                      {expense.business_date} · {expense.account_name} · {expense.payee || "—"}
                      {expense.requested_by_name ? ` · by ${expense.requested_by_name}` : ""}
                      {expense.rejection_reason ? ` · rejected: ${expense.rejection_reason}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-semibold">{expense.amount}</span>
                    <Badge tone={statusTone(expense.status)}>{expense.status.replace("_", " ")}</Badge>
                    {canApprove ? (
                      <>
                        <Button
                          size="sm"
                          onClick={() => actionMutation.mutate({ id: expense.id, action: "approve" })}
                          disabled={actionMutation.isPending}
                        >
                          Approve
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setRejectFor(expense)}>
                          Reject
                        </Button>
                      </>
                    ) : null}
                    {expense.status === "POSTED" && hasPerm("EXPENSE_POST") ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => actionMutation.mutate({ id: expense.id, action: "reverse", reason: "reversed from register" })}
                        disabled={actionMutation.isPending}
                      >
                        Reverse
                      </Button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
