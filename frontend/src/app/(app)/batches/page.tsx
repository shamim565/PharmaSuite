"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { BatchStatus, Branch, Medicine, MedicineBatch, Paginated } from "@/lib/types";

const emptyForm = {
  branch: "",
  medicine: "",
  batch_number: "",
  manufacturing_date: "",
  expiry_date: "",
  qty_received_total: "",
  qty_on_hand: "",
  unit_cost: "",
  notes: "",
};

function statusTone(status: BatchStatus): "green" | "slate" | "rose" | "amber" | "blue" {
  switch (status) {
    case "ACTIVE":
      return "green";
    case "EXPIRED":
      return "rose";
    case "QUARANTINE":
      return "amber";
    case "DAMAGED":
    case "RECALLED":
      return "rose";
    default:
      return "slate";
  }
}

function ExpiryCell({ batch }: { batch: MedicineBatch }) {
  if (!batch.expiry_date) return <span className="text-slate-400">—</span>;
  const days = batch.days_to_expiry ?? 0;
  return (
    <span className={days < 90 ? "font-medium text-amber-700" : ""}>
      {batch.expiry_date}
      {days < 0 ? " (expired)" : ` (${days}d)`}
    </span>
  );
}

export default function BatchesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [medicineFilter, setMedicineFilter] = useState("");
  const [form, setForm] = useState(emptyForm);

  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=200&status=ACTIVE"),
  });
  const medicinesQuery = useQuery({
    queryKey: ["medicines", "select"],
    queryFn: () => api.get<Paginated<Medicine>>("/medicines/?page_size=200&is_active=true"),
  });

  const params = new URLSearchParams({ page_size: "50" });
  if (search) params.set("search", search);
  if (status) params.set("status", status);

  const { data, isLoading, error } = useQuery({
    queryKey: ["batches", search, status],
    queryFn: () => api.get<Paginated<MedicineBatch>>(`/batches/?${params.toString()}`),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) =>
      api.post<MedicineBatch>("/batches/", {
        ...payload,
        manufacturing_date: payload.manufacturing_date || null,
        expiry_date: payload.expiry_date || null,
      }),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
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

  const filteredMedicines = (medicinesQuery.data?.results ?? []).filter((medicine) => {
    if (!medicineFilter) return true;
    const needle = medicineFilter.toLowerCase();
    return (
      medicine.name.toLowerCase().includes(needle) ||
      medicine.code.toLowerCase().includes(needle)
    );
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Batches & expiry</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "Add batch"}
        </Button>
      </div>

      {showForm ? (
        <Card>
          <CardHeader title="New batch" subtitle="Opening stock until the inventory ledger sprint takes over movements." />
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
            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-600">Medicine filter</span>
              <Input
                placeholder="Type to narrow list…"
                value={medicineFilter}
                onChange={(e) => setMedicineFilter(e.target.value)}
              />
            </div>
            <div className="col-span-2">
              <Field label="Medicine" error={fieldError("medicine")}>
                <Select
                  value={form.medicine}
                  onChange={(e) => setForm({ ...form, medicine: e.target.value })}
                  required
                >
                  <option value="">Select…</option>
                  {filteredMedicines.map((medicine) => (
                    <option key={medicine.id} value={medicine.id}>
                      {medicine.name} ({medicine.code})
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Field label="Batch number" error={fieldError("batch_number")}>
              <Input
                value={form.batch_number}
                onChange={(e) => setForm({ ...form, batch_number: e.target.value })}
                required
              />
            </Field>
            <Field label="Manufacturing date" error={fieldError("manufacturing_date")}>
              <Input
                type="date"
                value={form.manufacturing_date}
                onChange={(e) => setForm({ ...form, manufacturing_date: e.target.value })}
              />
            </Field>
            <Field label="Expiry date" error={fieldError("expiry_date")}>
              <Input
                type="date"
                value={form.expiry_date}
                onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
              />
            </Field>
            <Field label="Quantity received" error={fieldError("qty_received_total")}>
              <Input
                type="number"
                step="0.001"
                min="0"
                value={form.qty_received_total}
                onChange={(e) => setForm({ ...form, qty_received_total: e.target.value })}
                required
              />
            </Field>
            <Field label="Opening on hand" error={fieldError("qty_on_hand")}>
              <Input
                type="number"
                step="0.001"
                min="0"
                value={form.qty_on_hand}
                onChange={(e) => setForm({ ...form, qty_on_hand: e.target.value })}
                required
              />
            </Field>
            <Field label="Unit cost" error={fieldError("unit_cost")}>
              <Input
                type="number"
                step="0.0001"
                min="0"
                value={form.unit_cost}
                onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
                required
              />
            </Field>
            <Field label="Notes" error={fieldError("notes")}>
              <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Field>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Save batch"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Batch stock"
          subtitle={data ? `${data.count} batch(es)` : undefined}
          action={
            <div className="flex gap-2">
              <Input
                placeholder="Search batch / medicine…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-44"
              />
              <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-36">
                <option value="">All statuses</option>
                <option value="ACTIVE">Active</option>
                <option value="EXPIRED">Expired</option>
                <option value="QUARANTINE">Quarantine</option>
                <option value="DAMAGED">Damaged</option>
                <option value="DEPLETED">Depleted</option>
                <option value="RECALLED">Recalled</option>
              </Select>
            </div>
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No batches found." />
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Medicine</th>
                    <th className="px-4 py-2">Batch</th>
                    <th className="px-4 py-2">Expiry</th>
                    <th className="px-4 py-2 text-right">On hand</th>
                    <th className="px-4 py-2 text-right">Received</th>
                    <th className="px-4 py-2 text-right">Cost</th>
                    <th className="px-4 py-2">Branch</th>
                    <th className="px-4 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.results.map((batch) => (
                    <tr key={batch.id}>
                      <td className="px-4 py-2">
                        <span className="font-medium">{batch.medicine_name}</span>{" "}
                        <span className="font-mono text-xs text-slate-400">{batch.medicine_code}</span>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">{batch.batch_number}</td>
                      <td className="px-4 py-2">
                        <ExpiryCell batch={batch} />
                      </td>
                      <td className="px-4 py-2 text-right">{batch.qty_on_hand}</td>
                      <td className="px-4 py-2 text-right text-slate-500">{batch.qty_received_total}</td>
                      <td className="px-4 py-2 text-right">{batch.unit_cost}</td>
                      <td className="px-4 py-2 text-slate-500">{batch.branch_name}</td>
                      <td className="px-4 py-2">
                        <Badge tone={statusTone(batch.status)}>{batch.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="divide-y divide-slate-100 md:hidden">
              {data.results.map((batch) => (
                <li key={batch.id} className="space-y-1 p-4">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{batch.medicine_name}</p>
                    <Badge tone={statusTone(batch.status)}>{batch.status}</Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    {batch.medicine_code} · batch {batch.batch_number}
                  </p>
                  <p className="text-sm">
                    Expiry: <ExpiryCell batch={batch} />
                  </p>
                  <p className="text-sm">
                    On hand {batch.qty_on_hand} / received {batch.qty_received_total} @ {batch.unit_cost}
                  </p>
                  <p className="text-xs text-slate-400">{batch.branch_name}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </div>
  );
}
