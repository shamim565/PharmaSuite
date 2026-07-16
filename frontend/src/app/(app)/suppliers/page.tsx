"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Paginated, Supplier, SupplierLedgerResponse } from "@/lib/types";

const emptyForm = {
  code: "",
  name: "",
  supplier_type: "IMPORTER",
  contact_person: "",
  phone: "",
  credit_days: "30",
};

function LedgerPanel({ supplier, onClose }: { supplier: Supplier; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["supplier-ledger", supplier.id],
    queryFn: () => api.get<SupplierLedgerResponse>(`/suppliers/${supplier.id}/ledger/`),
  });

  return (
    <Card>
      <CardHeader
        title={`Ledger — ${supplier.name}`}
        subtitle={data ? `Balance: ${data.balance}` : undefined}
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

export default function SuppliersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [ledgerFor, setLedgerFor] = useState<Supplier | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["suppliers", search],
    queryFn: () =>
      api.get<Paginated<Supplier>>(`/suppliers/?page_size=50&search=${encodeURIComponent(search)}`),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) =>
      api.post<Supplier>("/suppliers/", { ...payload, credit_days: Number(payload.credit_days) }),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
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
        <h1 className="text-lg font-semibold text-slate-800">Suppliers</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "Add supplier"}
        </Button>
      </div>

      {ledgerFor ? <LedgerPanel supplier={ledgerFor} onClose={() => setLedgerFor(null)} /> : null}

      {showForm ? (
        <Card>
          <CardHeader title="New supplier" />
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
            <Field label="Type" error={fieldError("supplier_type")}>
              <Select
                value={form.supplier_type}
                onChange={(e) => setForm({ ...form, supplier_type: e.target.value })}
              >
                <option value="MANUFACTURER">Manufacturer</option>
                <option value="IMPORTER">Importer</option>
                <option value="TRADER">Trader</option>
                <option value="DISTRIBUTOR">Distributor</option>
              </Select>
            </Field>
            <Field label="Credit days" error={fieldError("credit_days")}>
              <Input
                type="number"
                min="0"
                value={form.credit_days}
                onChange={(e) => setForm({ ...form, credit_days: e.target.value })}
              />
            </Field>
            <Field label="Contact person" error={fieldError("contact_person")}>
              <Input
                value={form.contact_person}
                onChange={(e) => setForm({ ...form, contact_person: e.target.value })}
              />
            </Field>
            <Field label="Phone" error={fieldError("phone")}>
              <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Create supplier"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="All suppliers"
          subtitle={data ? `${data.count} supplier(s)` : undefined}
          action={
            <Input
              placeholder="Search name, phone…"
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
          <EmptyState message="No suppliers yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.results.map((supplier) => (
              <li key={supplier.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    {supplier.name} <span className="font-mono text-xs text-slate-400">{supplier.code}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {supplier.supplier_type} · credit {supplier.credit_days}d
                    {supplier.phone ? ` · ${supplier.phone}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm">
                    Payable:{" "}
                    <span className={Number(supplier.balance_cache) > 0 ? "font-semibold text-rose-700" : "text-slate-500"}>
                      {supplier.balance_cache}
                    </span>
                  </span>
                  {supplier.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                  <Button size="sm" variant="secondary" onClick={() => setLedgerFor(supplier)}>
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
