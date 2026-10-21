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
        subtitle={data ? `Balance: ${formatMoney(data.balance)}` : undefined}
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

export default function SuppliersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [ledgerFor, setLedgerFor] = useState<Supplier | null>(null);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  const params = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) params.set("search", debouncedSearch);

  const { data, isLoading, error } = useQuery({
    queryKey: ["suppliers", debouncedSearch, page],
    queryFn: () => api.get<Paginated<Supplier>>(`/suppliers/?${params.toString()}`),
  });

  const createMutation = useMutation({
    meta: { successMessage: "Supplier created" },
    mutationFn: (payload: typeof emptyForm) =>
      api.post<Supplier>("/suppliers/", { ...payload, credit_days: Number(payload.credit_days) }),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });

  const updateMutation = useMutation({
    meta: { successMessage: "Supplier updated" },
    mutationFn: (payload: typeof emptyForm) =>
      api.patch<Supplier>(`/suppliers/${editing?.id}/`, {
        ...payload,
        credit_days: Number(payload.credit_days),
      }),
    onSuccess: () => {
      setForm(emptyForm);
      setEditing(null);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });

  const statusMutation = useMutation({
    meta: { successMessage: "Supplier status updated" },
    mutationFn: ({ supplier, active }: { supplier: Supplier; active: boolean }) =>
      api.patch(`/suppliers/${supplier.id}/`, { is_active: active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate(form);
    } else {
      createMutation.mutate(form);
    }
  };

  const openEdit = (supplier: Supplier) => {
    setEditing(supplier);
    setForm({
      code: supplier.code,
      name: supplier.name,
      supplier_type: supplier.supplier_type,
      contact_person: supplier.contact_person,
      phone: supplier.phone,
      credit_days: String(supplier.credit_days),
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
        <h1 className="text-lg font-semibold text-slate-800">Suppliers</h1>
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
          {showForm ? "Close" : "Add supplier"}
        </Button>
      </div>

      {ledgerFor ? <LedgerPanel supplier={ledgerFor} onClose={() => setLedgerFor(null)} /> : null}

      {showForm ? (
        <Card>
          <CardHeader title={editing ? `Edit ${editing.name}` : "New supplier"} />
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
              <Input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </Field>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {createMutation.isPending || updateMutation.isPending
                  ? "Saving…"
                  : editing
                    ? "Save changes"
                    : "Create supplier"}
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
              aria-label="Search suppliers"
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
          <EmptyState message="No suppliers yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.results.map((supplier) => (
              <li
                key={supplier.id}
                className="flex flex-wrap items-center justify-between gap-2 p-4"
              >
                <div>
                  <p className="font-medium">
                    {supplier.name}{" "}
                    <span className="font-mono text-xs text-slate-500">{supplier.code}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {supplier.supplier_type} · credit {supplier.credit_days}d
                    {supplier.phone ? ` · ${supplier.phone}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm">
                    Payable:{" "}
                    <span
                      className={
                        Number(supplier.balance_cache) > 0
                          ? "font-semibold text-danger-700"
                          : "text-slate-500"
                      }
                    >
                      {formatMoney(supplier.balance_cache)}
                    </span>
                  </span>
                  {supplier.is_active ? (
                    <Badge tone="green">Active</Badge>
                  ) : (
                    <Badge>Inactive</Badge>
                  )}
                  <Button size="sm" variant="secondary" onClick={() => openEdit(supplier)}>
                    Edit
                  </Button>
                  {supplier.is_active ? (
                    <ConfirmButton
                      size="sm"
                      variant="ghost"
                      confirmLabel="Deactivate?"
                      onConfirm={() => statusMutation.mutate({ supplier, active: false })}
                      disabled={statusMutation.isPending}
                    >
                      Deactivate
                    </ConfirmButton>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => statusMutation.mutate({ supplier, active: true })}
                      disabled={statusMutation.isPending}
                    >
                      Activate
                    </Button>
                  )}
                  <Button size="sm" variant="secondary" onClick={() => setLedgerFor(supplier)}>
                    Ledger
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      apiDownload(
                        `/suppliers/${supplier.id}/statement/`,
                        `${supplier.code}-statement.csv`,
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
