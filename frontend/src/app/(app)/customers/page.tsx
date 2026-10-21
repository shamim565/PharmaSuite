"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import {
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmButton,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Pagination,
  Select,
  Spinner,
} from "@/components/ui";
import { ApiError, api, apiDownload } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type { Customer, CustomerLedgerResponse, Paginated } from "@/lib/types";

const emptyForm = {
  code: "",
  name: "",
  customer_type: "PHARMACY",
  phone: "",
  area: "",
  price_tier: "RETAIL",
  credit_limit: "0",
  credit_unlimited: false,
  credit_days: "0",
  default_discount_pct: "0",
  credit_hold: false,
  credit_hold_reason: "",
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
        subtitle={data ? `Due: ${formatMoney(data.balance)}` : undefined}
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
              <li
                key={entry.id}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm"
              >
                <div>
                  <p className="font-medium">{entry.entry_type}</p>
                  <p className="text-xs text-slate-500">
                    {entry.business_date ? formatDate(entry.business_date) : ""} ·{" "}
                    {entry.source_type}
                    {entry.source_number ? ` #${entry.source_number}` : ""}
                    {entry.due_date ? ` · due ${formatDate(entry.due_date)}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <span
                    className={`font-mono font-semibold ${positive ? "text-danger-700" : "text-primary-700"}`}
                  >
                    {positive ? "+" : "−"}
                    {formatMoney(Math.abs(Number(entry.amount_delta)))}
                  </span>
                  <span className="text-xs text-slate-500">
                    bal {formatMoney(entry.running_balance)}
                  </span>
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
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [ledgerFor, setLedgerFor] = useState<Customer | null>(null);
  const [editing, setEditing] = useState<Customer | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  const params = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) params.set("search", debouncedSearch);

  const { data, isLoading, error } = useQuery({
    queryKey: ["customers", debouncedSearch, page],
    queryFn: () => api.get<Paginated<Customer>>(`/customers/?${params.toString()}`),
  });

  const payloadFor = (payload: typeof emptyForm) => ({
    code: payload.code,
    name: payload.name,
    customer_type: payload.customer_type,
    phone: payload.phone,
    area: payload.area,
    price_tier: payload.price_tier,
    credit_limit: payload.credit_limit,
    credit_unlimited: payload.credit_unlimited,
    credit_days: Number(payload.credit_days),
    default_discount_pct: payload.default_discount_pct || "0",
    credit_hold: payload.credit_hold,
    credit_hold_reason: payload.credit_hold_reason,
  });

  const createMutation = useMutation({
    meta: { successMessage: "Customer created" },
    mutationFn: (payload: typeof emptyForm) =>
      api.post<Customer>("/customers/", payloadFor(payload)),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  const updateMutation = useMutation({
    meta: { successMessage: "Customer updated" },
    mutationFn: (payload: typeof emptyForm) =>
      api.patch<Customer>(`/customers/${editing?.id}/`, payloadFor(payload)),
    onSuccess: () => {
      setForm(emptyForm);
      setEditing(null);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  const statusMutation = useMutation({
    meta: { successMessage: "Customer status updated" },
    mutationFn: ({ customer, active }: { customer: Customer; active: boolean }) =>
      api.patch(`/customers/${customer.id}/`, { is_active: active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["customers"] }),
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate(form);
    } else {
      createMutation.mutate(form);
    }
  };

  const openEdit = (customer: Customer) => {
    setEditing(customer);
    setForm({
      code: customer.code,
      name: customer.name,
      customer_type: customer.customer_type,
      phone: customer.phone,
      area: customer.area,
      price_tier: customer.price_tier,
      credit_limit: customer.credit_limit,
      credit_unlimited: customer.credit_unlimited,
      credit_days: String(customer.credit_days),
      default_discount_pct: customer.default_discount_pct ?? "0",
      credit_hold: customer.credit_hold,
      credit_hold_reason: customer.credit_hold_reason ?? "",
    });
    setShowForm(true);
  };

  const fieldError = (name: string): string | null => {
    const err = updateMutation.error ?? createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Customers</h1>
        <Button
          size="sm"
          onClick={() => {
            if (showForm) {
              setShowForm(false);
              setEditing(null);
              setForm(emptyForm);
            } else {
              setEditing(null);
              setForm(emptyForm);
              setShowForm(true);
            }
          }}
        >
          {showForm ? "Close" : "Add customer"}
        </Button>
      </div>

      {ledgerFor ? <LedgerPanel customer={ledgerFor} onClose={() => setLedgerFor(null)} /> : null}

      {showForm ? (
        <Card>
          <CardHeader
            title={editing ? `Edit ${editing.name}` : "New customer"}
            subtitle="Credit limit 0 means cash-only."
          />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error} />
            </div>
            <Field label="Code" error={fieldError("code")}>
              <Input
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                required
              />
            </Field>
            <Field label="Name" error={fieldError("name")}>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </Field>
            <Field label="Type" error={fieldError("customer_type")}>
              <Select
                value={form.customer_type}
                onChange={(e) => setForm({ ...form, customer_type: e.target.value })}
              >
                <option value="PHARMACY">Pharmacy</option>
                <option value="RETAIL">Retail</option>
                <option value="HOSPITAL">Hospital</option>
                <option value="CLINIC">Clinic</option>
              </Select>
            </Field>
            <Field label="Phone" error={fieldError("phone")}>
              <Input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </Field>
            <Field label="Area" error={fieldError("area")}>
              <Input
                value={form.area}
                onChange={(e) => setForm({ ...form, area: e.target.value })}
              />
            </Field>
            <Field label="Price tier" error={fieldError("price_tier")}>
              <Select
                value={form.price_tier}
                onChange={(e) => setForm({ ...form, price_tier: e.target.value })}
              >
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
                value={form.credit_unlimited ? "0" : form.credit_limit}
                disabled={form.credit_unlimited}
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
            <Field label="Default discount %" error={fieldError("default_discount_pct")}>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={form.default_discount_pct}
                onChange={(e) => setForm({ ...form, default_discount_pct: e.target.value })}
              />
            </Field>
            <label className="flex items-end gap-2 pb-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={form.credit_unlimited}
                onChange={(e) => setForm({ ...form, credit_unlimited: e.target.checked })}
              />
              Unlimited credit
            </label>
            <label className="flex items-end gap-2 pb-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={form.credit_hold}
                onChange={(e) => setForm({ ...form, credit_hold: e.target.checked })}
              />
              Credit hold
            </label>
            {form.credit_hold ? (
              <Field label="Credit hold reason" error={fieldError("credit_hold_reason")}>
                <Input
                  value={form.credit_hold_reason}
                  onChange={(e) => setForm({ ...form, credit_hold_reason: e.target.value })}
                />
              </Field>
            ) : null}
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {createMutation.isPending || updateMutation.isPending
                  ? "Saving…"
                  : editing
                    ? "Save changes"
                    : "Create customer"}
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
              aria-label="Search customers"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
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
              <li
                key={customer.id}
                className="flex flex-wrap items-center justify-between gap-2 p-4"
              >
                <div>
                  <p className="font-medium">
                    {customer.name}{" "}
                    <span className="font-mono text-xs text-slate-500">{customer.code}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {customer.customer_type} · {customer.price_tier} · credit {customer.credit_days}
                    d
                    {customer.credit_unlimited
                      ? " · unlimited credit"
                      : Number(customer.credit_limit) > 0
                        ? ` · limit ${formatMoney(customer.credit_limit)}`
                        : ""}
                    {customer.area ? ` · ${customer.area}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {customer.credit_hold ? <Badge tone="rose">Credit hold</Badge> : null}
                  {customer.credit_unlimited ? <Badge tone="purple">Unlimited</Badge> : null}
                  {!customer.credit_unlimited &&
                  Number(customer.credit_limit) > 0 &&
                  Number(customer.balance_cache) > Number(customer.credit_limit) ? (
                    <Badge tone="rose">Over limit</Badge>
                  ) : null}
                  <span className="text-sm">
                    Due:{" "}
                    <span
                      className={
                        Number(customer.balance_cache) > 0
                          ? "font-semibold text-danger-700"
                          : "text-slate-500"
                      }
                    >
                      {formatMoney(customer.balance_cache)}
                    </span>
                  </span>
                  {customer.is_active ? (
                    <Badge tone="green">Active</Badge>
                  ) : (
                    <Badge>Inactive</Badge>
                  )}
                  <Button size="sm" variant="secondary" onClick={() => openEdit(customer)}>
                    Edit
                  </Button>
                  {customer.is_active ? (
                    <ConfirmButton
                      size="sm"
                      variant="ghost"
                      confirmLabel="Deactivate?"
                      onConfirm={() => statusMutation.mutate({ customer, active: false })}
                      disabled={statusMutation.isPending}
                    >
                      Deactivate
                    </ConfirmButton>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => statusMutation.mutate({ customer, active: true })}
                      disabled={statusMutation.isPending}
                    >
                      Activate
                    </Button>
                  )}
                  <Button size="sm" variant="secondary" onClick={() => setLedgerFor(customer)}>
                    Ledger
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      apiDownload(
                        `/customers/${customer.id}/statement/`,
                        `${customer.code}-statement.csv`,
                      )
                    }
                  >
                    Statement CSV
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {data && data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(data.previous)}
            hasNext={Boolean(data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
