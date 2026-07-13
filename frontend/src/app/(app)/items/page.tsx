"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Medicine, Paginated } from "@/lib/types";

const emptyForm = {
  code: "",
  name: "",
  generic_name: "",
  manufacturer: "",
  strength: "",
  unit: "tab",
  purchase_price: "",
  selling_price: "",
  mrp: "",
  reorder_level: "",
};

export default function ItemsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const { data, isLoading, error } = useQuery({
    queryKey: ["medicines", search],
    queryFn: () =>
      api.get<Paginated<Medicine>>(`/medicines/?page_size=50&search=${encodeURIComponent(search)}`),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) => api.post<Medicine>("/medicines/", payload),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["medicines"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (medicine: Medicine) =>
      api.patch<Medicine>(`/medicines/${medicine.id}/`, { is_active: !medicine.is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["medicines"] });
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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Items</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "Add item"}
        </Button>
      </div>

      {showForm ? (
        <Card>
          <CardHeader title="New item" subtitle="Catalog fields can be extended in the catalog sprint." />
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
            <Field label="Generic" error={fieldError("generic_name")}>
              <Input
                value={form.generic_name}
                onChange={(e) => setForm({ ...form, generic_name: e.target.value })}
              />
            </Field>
            <Field label="Manufacturer" error={fieldError("manufacturer")}>
              <Input
                value={form.manufacturer}
                onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
              />
            </Field>
            <Field label="Strength" error={fieldError("strength")}>
              <Input value={form.strength} onChange={(e) => setForm({ ...form, strength: e.target.value })} />
            </Field>
            <Field label="Unit" error={fieldError("unit")}>
              <Input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
            </Field>
            <Field label="Purchase price" error={fieldError("purchase_price")}>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={form.purchase_price}
                onChange={(e) => setForm({ ...form, purchase_price: e.target.value })}
                required
              />
            </Field>
            <Field label="Selling price" error={fieldError("selling_price")}>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={form.selling_price}
                onChange={(e) => setForm({ ...form, selling_price: e.target.value })}
                required
              />
            </Field>
            <Field label="MRP" error={fieldError("mrp")}>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={form.mrp}
                onChange={(e) => setForm({ ...form, mrp: e.target.value })}
              />
            </Field>
            <Field label="Reorder level" error={fieldError("reorder_level")}>
              <Input
                type="number"
                step="1"
                min="0"
                value={form.reorder_level}
                onChange={(e) => setForm({ ...form, reorder_level: e.target.value })}
              />
            </Field>
            <div className="col-span-2 flex items-end lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Save item"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Catalog"
          subtitle={data ? `${data.count} item(s)` : undefined}
          action={
            <Input
              placeholder="Search name, generic, code…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-56"
            />
          }
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No items yet. Add your first medicine." />
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Code</th>
                    <th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">Generic</th>
                    <th className="px-4 py-2">Unit</th>
                    <th className="px-4 py-2 text-right">Purchase</th>
                    <th className="px-4 py-2 text-right">Selling</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.results.map((medicine) => (
                    <tr key={medicine.id}>
                      <td className="px-4 py-2 font-mono text-xs">{medicine.code}</td>
                      <td className="px-4 py-2 font-medium">{medicine.name}</td>
                      <td className="px-4 py-2 text-slate-500">{medicine.generic_name || "—"}</td>
                      <td className="px-4 py-2">{medicine.unit}</td>
                      <td className="px-4 py-2 text-right">{medicine.purchase_price}</td>
                      <td className="px-4 py-2 text-right">{medicine.selling_price}</td>
                      <td className="px-4 py-2">
                        {medicine.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => toggleMutation.mutate(medicine)}
                          disabled={toggleMutation.isPending}
                        >
                          {medicine.is_active ? "Deactivate" : "Activate"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <ul className="divide-y divide-slate-100 md:hidden">
              {data.results.map((medicine) => (
                <li key={medicine.id} className="space-y-1 p-4">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{medicine.name}</p>
                    {medicine.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                  </div>
                  <p className="text-xs text-slate-500">
                    {medicine.code} · {medicine.generic_name || "no generic"} · {medicine.unit}
                  </p>
                  <p className="text-sm">
                    Purchase {medicine.purchase_price} · Selling {medicine.selling_price}
                  </p>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => toggleMutation.mutate(medicine)}
                    disabled={toggleMutation.isPending}
                  >
                    {medicine.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </div>
  );
}
