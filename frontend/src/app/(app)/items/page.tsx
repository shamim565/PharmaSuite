"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Select,
  Spinner,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type {
  Generic,
  Manufacturer,
  Medicine,
  MedicineCategory,
  MedicineUnitConversion,
  Paginated,
  Unit,
} from "@/lib/types";

const emptyForm = {
  code: "",
  name: "",
  generic: "",
  manufacturer: "",
  category: "",
  base_unit: "",
  strength: "",
  dosage_form: "",
  barcode: "",
  purchase_price: "",
  selling_price: "",
  mrp: "",
  reorder_level: "",
  shelf_life_months: "",
  no_batch: false,
  rx_required: false,
  cold_chain: false,
};

function ConversionsPanel({
  medicine,
  units,
  onClose,
}: {
  medicine: Medicine;
  units: Unit[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [unitId, setUnitId] = useState("");
  const [factor, setFactor] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["conversions", medicine.id],
    queryFn: () => api.get<MedicineUnitConversion[]>(`/medicines/${medicine.id}/conversions/`),
  });

  const addMutation = useMutation({
    mutationFn: () =>
      api.post(`/medicines/${medicine.id}/conversions/`, { unit: unitId, factor_to_base: factor }),
    onSuccess: () => {
      setUnitId("");
      setFactor("");
      queryClient.invalidateQueries({ queryKey: ["conversions", medicine.id] });
      queryClient.invalidateQueries({ queryKey: ["medicines"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/medicines/conversions/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversions", medicine.id] }),
  });

  return (
    <Card>
      <CardHeader
        title={`Pack conversions — ${medicine.name}`}
        subtitle="Base unit is used for all stock quantities."
        action={
          <Button size="sm" variant="secondary" onClick={onClose}>
            Close
          </Button>
        }
      />
      <div className="space-y-3 p-4">
        <ErrorBanner error={addMutation.error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.length === 0 ? (
          <EmptyState message="No conversions yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.map((conversion) => (
              <li key={conversion.id} className="flex items-center justify-between py-2 text-sm">
                <span>
                  1 {conversion.unit_name} = <strong>{conversion.factor_to_base}</strong>{" "}
                  {medicine.base_unit_name || "base"}
                  {conversion.is_purchase_default ? <Badge tone="blue">purchase</Badge> : null}
                  {conversion.is_sale_default ? <Badge tone="green">sale</Badge> : null}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => deleteMutation.mutate(conversion.id)}
                  disabled={deleteMutation.isPending}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-end gap-2">
          <div className="w-40">
            <Field label="Unit">
              <Select value={unitId} onChange={(e) => setUnitId(e.target.value)}>
                <option value="">Select…</option>
                {units
                  .filter((u) => u.id !== medicine.base_unit)
                  .map((unit) => (
                    <option key={unit.id} value={unit.id}>
                      {unit.name}
                    </option>
                  ))}
              </Select>
            </Field>
          </div>
          <div className="w-40">
            <Field label="Factor to base">
              <Input
                type="number"
                step="0.000001"
                min="0.000001"
                value={factor}
                onChange={(e) => setFactor(e.target.value)}
              />
            </Field>
          </div>
          <Button
            size="sm"
            onClick={() => addMutation.mutate()}
            disabled={!unitId || !factor || addMutation.isPending}
          >
            Add conversion
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function ItemsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [conversionsFor, setConversionsFor] = useState<Medicine | null>(null);

  const genericsQuery = useQuery({
    queryKey: ["generics", "select"],
    queryFn: () => api.get<Paginated<Generic>>("/generics/?page_size=200&is_active=true"),
  });
  const manufacturersQuery = useQuery({
    queryKey: ["manufacturers", "select"],
    queryFn: () => api.get<Paginated<Manufacturer>>("/manufacturers/?page_size=200&is_active=true"),
  });
  const categoriesQuery = useQuery({
    queryKey: ["categories", "select"],
    queryFn: () =>
      api.get<Paginated<MedicineCategory>>("/medicine-categories/?page_size=200&is_active=true"),
  });
  const unitsQuery = useQuery({
    queryKey: ["units", "select"],
    queryFn: () => api.get<Paginated<Unit>>("/units/?page_size=200&is_active=true"),
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["medicines", search],
    queryFn: () =>
      api.get<Paginated<Medicine>>(`/medicines/?page_size=50&search=${encodeURIComponent(search)}`),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) =>
      api.post<Medicine>("/medicines/", {
        ...payload,
        generic: payload.generic || null,
        manufacturer: payload.manufacturer || null,
        category: payload.category || null,
        base_unit: payload.base_unit || null,
        shelf_life_months: payload.shelf_life_months ? Number(payload.shelf_life_months) : null,
      }),
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

  const flags = (medicine: Medicine) => (
    <>
      {medicine.rx_required ? <Badge tone="amber">Rx</Badge> : null}
      {medicine.cold_chain ? <Badge tone="blue">Cold</Badge> : null}
      {medicine.no_batch ? <Badge>No batch</Badge> : null}
    </>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Items</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "Add item"}
        </Button>
      </div>

      {conversionsFor ? (
        <ConversionsPanel
          medicine={conversionsFor}
          units={unitsQuery.data?.results ?? []}
          onClose={() => setConversionsFor(null)}
        />
      ) : null}

      {showForm ? (
        <Card>
          <CardHeader title="New item" subtitle="Catalog masters keep generics, manufacturers and units consistent." />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error} />
            </div>
            <Field label="Code (SKU)" error={fieldError("code")}>
              <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
            </Field>
            <Field label="Name" error={fieldError("name")}>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Generic" error={fieldError("generic")}>
              <Select value={form.generic} onChange={(e) => setForm({ ...form, generic: e.target.value })}>
                <option value="">—</option>
                {genericsQuery.data?.results.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Manufacturer" error={fieldError("manufacturer")}>
              <Select
                value={form.manufacturer}
                onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
              >
                <option value="">—</option>
                {manufacturersQuery.data?.results.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Category" error={fieldError("category")}>
              <Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="">—</option>
                {categoriesQuery.data?.results.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Base unit" error={fieldError("base_unit")}>
              <Select
                value={form.base_unit}
                onChange={(e) => setForm({ ...form, base_unit: e.target.value })}
              >
                <option value="">—</option>
                {unitsQuery.data?.results.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Strength" error={fieldError("strength")}>
              <Input value={form.strength} onChange={(e) => setForm({ ...form, strength: e.target.value })} />
            </Field>
            <Field label="Dosage form" error={fieldError("dosage_form")}>
              <Input
                value={form.dosage_form}
                onChange={(e) => setForm({ ...form, dosage_form: e.target.value })}
                placeholder="tablet / syrup…"
              />
            </Field>
            <Field label="Barcode" error={fieldError("barcode")}>
              <Input value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value })} />
            </Field>
            <Field label="Shelf life (months)" error={fieldError("shelf_life_months")}>
              <Input
                type="number"
                min="0"
                value={form.shelf_life_months}
                onChange={(e) => setForm({ ...form, shelf_life_months: e.target.value })}
              />
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
            <div className="col-span-2 flex flex-wrap items-center gap-4 lg:col-span-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.rx_required}
                  onChange={(e) => setForm({ ...form, rx_required: e.target.checked })}
                />
                Prescription required
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.cold_chain}
                  onChange={(e) => setForm({ ...form, cold_chain: e.target.checked })}
                />
                Cold chain
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.no_batch}
                  onChange={(e) => setForm({ ...form, no_batch: e.target.checked })}
                />
                No batch/expiry
              </label>
            </div>
            <div className="col-span-2 lg:col-span-4">
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
              placeholder="Search name, generic, code, barcode…"
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
                    <th className="px-4 py-2">Flags</th>
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
                      <td className="px-4 py-2">{medicine.base_unit_name || "—"}</td>
                      <td className="px-4 py-2 text-right">{medicine.purchase_price}</td>
                      <td className="px-4 py-2 text-right">{medicine.selling_price}</td>
                      <td className="space-x-1 px-4 py-2">{flags(medicine)}</td>
                      <td className="px-4 py-2">
                        {medicine.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                      </td>
                      <td className="space-x-1 px-4 py-2 text-right">
                        <Button size="sm" variant="ghost" onClick={() => setConversionsFor(medicine)}>
                          Units
                        </Button>
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

            <ul className="divide-y divide-slate-100 md:hidden">
              {data.results.map((medicine) => (
                <li key={medicine.id} className="space-y-1 p-4">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{medicine.name}</p>
                    {medicine.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                  </div>
                  <p className="text-xs text-slate-500">
                    {medicine.code} · {medicine.generic_name || "no generic"} ·{" "}
                    {medicine.base_unit_name || "no unit"}
                  </p>
                  <p className="text-sm">
                    Purchase {medicine.purchase_price} · Selling {medicine.selling_price}
                  </p>
                  <div className="flex flex-wrap gap-1">{flags(medicine)}</div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" onClick={() => setConversionsFor(medicine)}>
                      Units
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => toggleMutation.mutate(medicine)}
                      disabled={toggleMutation.isPending}
                    >
                      {medicine.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </div>
  );
}
