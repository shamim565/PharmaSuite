"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Customer, CustomerLedgerResponse, Paginated } from "@/lib/types";

const emptyForm = {
  code: "",
  name: "",
  customer_type: "PHARMACY",
  phone: "",
  area: "",
  price_tier: "RETAIL",
  credit_limit: "0",
  credit_days: "0",
};

function LedgerPanel({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["customer-ledger", customer.id],
    queryFn: () => api.get<CustomerLedgerResponse>(`/customers/${customer.id}/ledger/`),
  });

  return (
    <Card>
      <CardHeader
        title={`Ledger — ${customer.name}`}
        subtitle={data ? `Due: ${data.balance}` : undefined}
        action={
          <Button size="sm" variant="secondary" onClick={onClose}>
            Close
          </Button>
        }
      />
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : !data || data.results.length === 0 ? (
        <EmptyState message="No ledger entries yet." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {data.results.map((entry) => {
            const positive = !entry.amount_delta.startsWith("-");
            return (
              <li key={entry.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
                <div>
                  <p className="font-medium">{entry.entry_type}</p>
                  <p className="text-xs text-slate-500">
                    {entry.business_date} · {entry.source_type}
                    {entry.source_number ? ` #${entry.source_number}` : ""}
                    {entry.due_date ? ` · due ${entry.due_date}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <span className={`font-mono font-semibold ${positive ? "text-rose-700" : "text-emerald-700"}`}>
                    {positive ? "+" : ""}
                    {entry.amount_delta}
                  </span>
                  <span className="text-xs text-slate-500">bal {entry.running_balance}</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

export default function CustomersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [ledgerFor, setLedgerFor] = useState<Customer | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["customers", search],
    queryFn: () =>
      api.get<Paginated<Customer>>(`/customers/?page_size=50&search=${encodeURIComponent(search)}`),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) =>
      api.post<Customer>("/customers/", {
        ...payload,
        credit_limit: payload.credit_limit,
        credit_days: Number(payload.credit_days),
      }),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["customers"] });
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
        <h1 className="text-lg font-semibold text-slate-800">Customers</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "Add customer"}
        </Button>
      </div>

      {ledgerFor ? <LedgerPanel customer={ledgerFor} onClose={() => setLedgerFor(null)} /> : null}

      {showForm ? (
        <Card>
          <CardHeader title="New customer" subtitle="Credit limit 0 means cash-only." />
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
            <Field label="Type" error={fieldError("customer_type")}>
              <Select value={form.customer_type} onChange={(e) => setForm({ ...form, customer_type: e.target.value })}>
                <option value="PHARMACY">Pharmacy</option>
                <option value="RETAIL">Retail</option>
                <option value="HOSPITAL">Hospital</option>
                <option value="CLINIC">Clinic</option>
              </Select>
            </Field>
            <Field label="Phone" error={fieldError("phone")}>
              <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="Area" error={fieldError("area")}>
              <Input value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} />
            </Field>
            <Field label="Price tier" error={fieldError("price_tier")}>
              <Select value={form.price_tier} onChange={(e) => setForm({ ...form, price_tier: e.target.value })}>
                <option value="RETAIL">Retail</option>
                <option value="WHOLESALE">Wholesale</option>
                <option value="CUSTOM">Custom</option>
              </Select>
            </Field>
            <Field label="Credit limit" error={fieldError("credit_limit")}>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={form.credit_limit}
                onChange={(e) => setForm({ ...form, credit_limit: e.target.value })}
              />
            </Field>
            <Field label="Credit days" error={fieldError("credit_days")}>
              <Input
                type="number"
                min="0"
                value={form.credit_days}
                onChange={(e) => setForm({ ...form, credit_days: e.target.value })}
              />
            </Field>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Create customer"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="All customers"
          subtitle={data ? `${data.count} customer(s)` : undefined}
          action={
            <Input
              placeholder="Search name, phone, area…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48"
            />
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No customers yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.results.map((customer) => (
              <li key={customer.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    {customer.name} <span className="font-mono text-xs text-slate-400">{customer.code}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {customer.customer_type} · {customer.price_tier} · credit {customer.credit_days}d
                    {customer.area ? ` · ${customer.area}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {customer.credit_hold ? <Badge tone="rose">Credit hold</Badge> : null}
                  <span className="text-sm">
                    Due:{" "}
                    <span className={Number(customer.balance_cache) > 0 ? "font-semibold text-rose-700" : "text-slate-500"}>
                      {customer.balance_cache}
                    </span>
                  </span>
                  {customer.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                  <Button size="sm" variant="secondary" onClick={() => setLedgerFor(customer)}>
                    Ledger
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
