"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type {
  AccountLedgerResponse,
  Branch,
  FinancialAccount,
  Paginated,
} from "@/lib/types";

const emptyAccount = {
  code: "",
  name: "",
  account_type: "BANK",
  branch: "",
  provider: "",
  account_number: "",
};

function AccountPanel({ account, onClose }: { account: FinancialAccount; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [transferTo, setTransferTo] = useState("");
  const [transferAmount, setTransferAmount] = useState("");
  const [transferReference, setTransferReference] = useState("");

  const ledgerQuery = useQuery({
    queryKey: ["account-ledger", account.id],
    queryFn: () => api.get<AccountLedgerResponse>(`/accounts/${account.id}/ledger/`),
  });
  const accountsQuery = useQuery({
    queryKey: ["accounts", "select"],
    queryFn: () => api.get<Paginated<FinancialAccount>>("/accounts/?page_size=50&is_active=true"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["account-ledger", account.id] });
    queryClient.invalidateQueries({ queryKey: ["accounts"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const depositMutation = useMutation({
    meta: { successMessage: "Deposit posted" },
    mutationFn: () => api.post(`/accounts/${account.id}/deposit/`, { amount, reference }),
    onSuccess: () => {
      setAmount("");
      setReference("");
      invalidate();
    },
  });
  const withdrawMutation = useMutation({
    meta: { successMessage: "Withdrawal posted" },
    mutationFn: () => api.post(`/accounts/${account.id}/withdraw/`, { amount, reference }),
    onSuccess: () => {
      setAmount("");
      setReference("");
      invalidate();
    },
  });
  const transferMutation = useMutation({
    meta: { successMessage: "Transfer completed" },
    mutationFn: () =>
      api.post("/accounts/transfer/", {
        from_account: account.id,
        to_account: transferTo,
        amount: transferAmount,
        reference: transferReference,
      }),
    onSuccess: () => {
      setTransferAmount("");
      setTransferReference("");
      invalidate();
    },
  });

  return (
    <Card>
      <CardHeader
        title={`${account.name} (${account.code})`}
        subtitle={`${account.account_type} · balance ${formatMoney(account.balance_cache)}`}
        action={
          <Button size="sm" variant="secondary" onClick={onClose}>
            Close
          </Button>
        }
      />
      <div className="space-y-4 p-4">
        {hasPerm("ACCOUNT_MANAGE") ? (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
            <div className="col-span-2">
              <Field label="Amount">
                <Input type="number" step="0.01" min="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
              </Field>
            </div>
            <div className="col-span-2">
              <Field label="Reference">
                <Input value={reference} onChange={(e) => setReference(e.target.value)} />
              </Field>
            </div>
            <div className="flex items-end gap-2 lg:col-span-2">
              <Button
                size="sm"
                onClick={() => depositMutation.mutate()}
                disabled={depositMutation.isPending || !amount}
              >
                Deposit
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => withdrawMutation.mutate()}
                disabled={withdrawMutation.isPending || !amount}
              >
                Withdraw
              </Button>
            </div>
            <div className="col-span-2 lg:col-span-6">
              <ErrorBanner error={depositMutation.error ?? withdrawMutation.error} />
            </div>
            <div className="col-span-2">
              <Field label="Transfer to">
                <Select value={transferTo} onChange={(e) => setTransferTo(e.target.value)}>
                  <option value="">Select…</option>
                  {accountsQuery.data?.results
                    .filter((item) => item.id !== account.id)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} ({formatMoney(item.balance_cache)})
                      </option>
                    ))}
                </Select>
              </Field>
            </div>
            <div className="col-span-2">
              <Field label="Transfer amount">
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={transferAmount}
                  onChange={(e) => setTransferAmount(e.target.value)}
                />
              </Field>
            </div>
            <div className="col-span-2">
              <Field label="Transfer reference">
                <Input value={transferReference} onChange={(e) => setTransferReference(e.target.value)} />
              </Field>
            </div>
            <div className="flex items-end lg:col-span-1">
              <Button
                size="sm"
                onClick={() => transferMutation.mutate()}
                disabled={transferMutation.isPending || !transferTo || !transferAmount}
              >
                Transfer
              </Button>
            </div>
            <div className="col-span-2 lg:col-span-6">
              <ErrorBanner error={transferMutation.error} />
            </div>
          </div>
        ) : null}

        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Account ledger</p>
          <ErrorBanner error={ledgerQuery.error} />
          {ledgerQuery.isLoading ? (
            <Spinner />
          ) : !ledgerQuery.data || ledgerQuery.data.results.length === 0 ? (
            <EmptyState message="No transactions yet." />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {ledgerQuery.data.results.map((entry) => {
                const positive = !entry.amount_delta.startsWith("-");
                return (
                  <li key={entry.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                    <div>
                      <p className="font-medium">{entry.entry_type.replace(/_/g, " ")}</p>
                      <p className="text-xs text-slate-500">
                        {formatDate(entry.business_date)} · {entry.source_type}
                        {entry.source_number ? ` #${entry.source_number}` : ""}
                        {entry.reference ? ` · ${entry.reference}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className={`font-mono font-semibold ${positive ? "text-primary-700" : "text-danger-700"}`}>
                        {positive ? "+" : "−"}
                        {formatMoney(Math.abs(Number(entry.amount_delta)))}
                      </span>
                      <span className="text-xs text-slate-500">bal {formatMoney(entry.running_balance)}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyAccount);
  const [selected, setSelected] = useState<FinancialAccount | null>(null);

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<Paginated<FinancialAccount>>("/accounts/?page_size=50"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });

  const createMutation = useMutation({
    meta: { successMessage: "Account created" },
    mutationFn: (payload: typeof emptyAccount) =>
      api.post<FinancialAccount>("/accounts/", { ...payload, branch: payload.branch || null }),
    onSuccess: () => {
      setForm(emptyAccount);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
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

  const total = (accountsQuery.data?.results ?? []).reduce(
    (sum, account) => sum + Number(account.balance_cache),
    0,
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Accounts</h1>
        {hasPerm("ACCOUNT_MANAGE") ? (
          <Button size="sm" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Close" : "Add account"}
          </Button>
        ) : null}
      </div>

      <Card className="p-4">
        <p className="text-xs uppercase text-slate-500">Total balance</p>
        <p className="text-2xl font-bold text-primary-700">{formatMoney(total)}</p>
      </Card>

      {selected ? <AccountPanel account={selected} onClose={() => setSelected(null)} /> : null}

      {showForm && hasPerm("ACCOUNT_MANAGE") ? (
        <Card>
          <CardHeader title="New account" subtitle="Cash, bank or mobile financial service wallet." />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error} />
            </div>
            <Field label="Code" error={fieldError("code")}>
              <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
            </Field>
            <Field label="Name" error={fieldError("name")}>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Type" error={fieldError("account_type")}>
              <Select value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value })}>
                <option value="CASH">Cash</option>
                <option value="BANK">Bank</option>
                <option value="MFS">MFS wallet</option>
              </Select>
            </Field>
            <Field label="Branch" error={fieldError("branch")}>
              <Select value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })}>
                <option value="">Company-level</option>
                {branchesQuery.data?.results.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Provider" error={fieldError("provider")}>
              <Input value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} />
            </Field>
            <Field label="Account number" error={fieldError("account_number")}>
              <Input
                value={form.account_number}
                onChange={(e) => setForm({ ...form, account_number: e.target.value })}
              />
            </Field>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Create account"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="All accounts" subtitle={accountsQuery.data ? `${accountsQuery.data.count} account(s)` : undefined} />
        <ErrorBanner error={accountsQuery.error} />
        {accountsQuery.isLoading ? (
          <Spinner />
        ) : !accountsQuery.data || accountsQuery.data.results.length === 0 ? (
          <EmptyState message="No accounts yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {accountsQuery.data.results.map((account) => (
              <li key={account.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    {account.name} <span className="font-mono text-xs text-slate-500">{account.code}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {account.account_type}
                    {account.branch_name ? ` · ${account.branch_name}` : " · company-level"}
                    {account.provider ? ` · ${account.provider}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className={`font-mono font-semibold ${Number(account.balance_cache) < 0 ? "text-danger-700" : "text-slate-800"}`}>
                    {formatMoney(account.balance_cache)}
                  </span>
                  {account.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                  <Button size="sm" variant="secondary" onClick={() => setSelected(account)}>
                    Ledger & operations
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
