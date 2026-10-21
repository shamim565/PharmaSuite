"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Pagination,
  Select,
  Spinner,
} from "@/components/ui";
import { MedicineCombobox } from "@/components/medicine-combobox";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type { BatchStatus, Branch, MedicineBatch, Paginated, WarehouseLocation } from "@/lib/types";

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
  if (!batch.expiry_date) return <span className="text-slate-500">—</span>;
  const days = batch.days_to_expiry ?? 0;
  return (
    <span className={days < 90 ? "font-medium text-amber-700" : ""}>
      {formatDate(batch.expiry_date)}
      {days < 0 ? " (expired)" : ` (${days}d)`}
    </span>
  );
}

const emptyLocation = { branch: "", zone: "", rack: "", bin: "" };

function WarehouseLocationsCard() {
  const { hasPerm, user } = useAuth();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...emptyLocation, branch: user?.default_branch_id ?? "" });

  const locationsQuery = useQuery({
    queryKey: ["warehouse-locations"],
    queryFn: () =>
      api.get<Paginated<WarehouseLocation>>("/inventory/locations/?page_size=200&is_active=true"),
  });

  const createMutation = useMutation({
    meta: { successMessage: "Location added" },
    mutationFn: () =>
      api.post<WarehouseLocation>("/inventory/locations/", {
        ...form,
        branch: form.branch || undefined,
        zone: form.zone || "",
        rack: form.rack || "",
      }),
    onSuccess: () => {
      setForm({ ...emptyLocation, branch: user?.default_branch_id ?? "" });
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["warehouse-locations"] });
    },
  });

  const deactivateMutation = useMutation({
    meta: { successMessage: "Location deactivated" },
    mutationFn: (id: string) => api.patch(`/inventory/locations/${id}/`, { is_active: false }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["warehouse-locations"] }),
  });

  return (
    <Card>
      <CardHeader
        title="Warehouse locations"
        subtitle={
          locationsQuery.data
            ? `${locationsQuery.data.count} active zone/rack/bin location(s)`
            : undefined
        }
        action={
          hasPerm("STOCK_ADJUST") ? (
            <Button size="sm" variant="secondary" onClick={() => setShowForm((v) => !v)}>
              {showForm ? "Close" : "Add location"}
            </Button>
          ) : undefined
        }
      />
      {showForm ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
          className="grid grid-cols-2 gap-3 border-b border-slate-100 p-4 lg:grid-cols-5"
        >
          <Field label="Zone">
            <Input
              value={form.zone}
              onChange={(e) => setForm({ ...form, zone: e.target.value })}
              placeholder="A / Cold room"
            />
          </Field>
          <Field label="Rack">
            <Input
              value={form.rack}
              onChange={(e) => setForm({ ...form, rack: e.target.value })}
              placeholder="R1"
            />
          </Field>
          <Field label="Bin">
            <Input
              value={form.bin}
              onChange={(e) => setForm({ ...form, bin: e.target.value })}
              placeholder="B3"
              required
            />
          </Field>
          <div className="flex items-end">
            <Button size="sm" type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
          <ErrorBanner error={createMutation.error} />
        </form>
      ) : null}
      {locationsQuery.isLoading ? (
        <Spinner />
      ) : !locationsQuery.data || locationsQuery.data.results.length === 0 ? (
        <p className="p-4 text-sm text-slate-500">No locations defined yet.</p>
      ) : (
        <ul className="flex flex-wrap gap-2 p-4">
          {locationsQuery.data.results.map((loc) => (
            <li
              key={loc.id}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm"
            >
              <span className="font-mono text-xs font-medium">{loc.label}</span>
              <span className="text-xs text-slate-500">{loc.branch_name}</span>
              {hasPerm("STOCK_ADJUST") ? (
                <button
                  type="button"
                  aria-label={`Deactivate ${loc.label}`}
                  className="text-xs text-slate-400 hover:text-danger-600"
                  onClick={() => deactivateMutation.mutate(loc.id)}
                >
                  ✕
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function BatchesPage() {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [location, setLocation] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const debouncedSearch = useDebouncedValue(search);

  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=200&status=ACTIVE"),
  });
  const locationsQuery = useQuery({
    queryKey: ["warehouse-locations"],
    queryFn: () => api.get<Paginated<WarehouseLocation>>("/inventory/locations/?page_size=200"),
  });

  const params = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) params.set("search", debouncedSearch);
  if (status) params.set("status", status);
  if (location) params.set("location", location);

  const { data, isLoading, error } = useQuery({
    queryKey: ["batches", debouncedSearch, status, location, page],
    queryFn: () => api.get<Paginated<MedicineBatch>>(`/batches/?${params.toString()}`),
  });

  const createMutation = useMutation({
    meta: { successMessage: "Batch created" },
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

  const setBatchLocationMutation = useMutation({
    meta: { successMessage: "Batch location updated" },
    mutationFn: ({ batch, loc }: { batch: MedicineBatch; loc: string }) =>
      api.patch(`/batches/${batch.id}/`, { location: loc }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["batches"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Batches & expiry</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "Add batch"}
        </Button>
      </div>

      <WarehouseLocationsCard />

      {showForm ? (
        <Card>
          <CardHeader
            title="New batch"
            subtitle="Opening quantity posts to the inventory ledger."
          />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error} />
            </div>
            <Field label="Branch" error={fieldError("branch")}>
              <Select
                value={form.branch}
                onChange={(e) => setForm({ ...form, branch: e.target.value })}
                required
              >
                <option value="">Select…</option>
                {branchesQuery.data?.results.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="col-span-2">
              <Field label="Medicine" error={fieldError("medicine")}>
                <MedicineCombobox
                  value={form.medicine}
                  onChange={(id) => setForm((current) => ({ ...current, medicine: id }))}
                />
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
              <Input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
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
                aria-label="Search batches"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-44"
              />
              <Select
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setPage(1);
                }}
                className="w-36"
              >
                <option value="">All statuses</option>
                <option value="ACTIVE">Active</option>
                <option value="EXPIRED">Expired</option>
                <option value="QUARANTINE">Quarantine</option>
                <option value="DAMAGED">Damaged</option>
                <option value="DEPLETED">Depleted</option>
                <option value="RECALLED">Recalled</option>
              </Select>
              <Select
                value={location}
                onChange={(e) => {
                  setLocation(e.target.value);
                  setPage(1);
                }}
                className="w-40"
                aria-label="Filter by location"
              >
                <option value="">All locations</option>
                {locationsQuery.data?.results.map((loc) => (
                  <option key={loc.id} value={loc.label}>
                    {loc.label}
                  </option>
                ))}
                {location && !locationsQuery.data?.results.some((loc) => loc.label === location) ? (
                  <option value={location}>{location}</option>
                ) : null}
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
                    <th className="px-4 py-2">Location</th>
                    <th className="px-4 py-2">Branch</th>
                    <th className="px-4 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.results.map((batch) => (
                    <tr key={batch.id}>
                      <td className="px-4 py-2">
                        <span className="font-medium">{batch.medicine_name}</span>{" "}
                        <span className="font-mono text-xs text-slate-500">
                          {batch.medicine_code}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">{batch.batch_number}</td>
                      <td className="px-4 py-2">
                        <ExpiryCell batch={batch} />
                      </td>
                      <td className="px-4 py-2 text-right">{formatQty(batch.qty_on_hand)}</td>
                      <td className="px-4 py-2 text-right text-slate-500">
                        {formatQty(batch.qty_received_total)}
                      </td>
                      <td className="px-4 py-2 text-right">{formatMoney(batch.unit_cost)}</td>
                      <td className="px-4 py-2">
                        {hasPerm("STOCK_ADJUST") ? (
                          <Select
                            value={batch.location}
                            onChange={(e) =>
                              setBatchLocationMutation.mutate({
                                batch,
                                loc: e.target.value,
                              })
                            }
                            className="w-28 py-1 text-xs"
                            aria-label={`Location for batch ${batch.batch_number}`}
                          >
                            <option value="">—</option>
                            {locationsQuery.data?.results.map((loc) => (
                              <option key={loc.id} value={loc.label}>
                                {loc.label}
                              </option>
                            ))}
                            {batch.location &&
                            !locationsQuery.data?.results.some(
                              (loc) => loc.label === batch.location,
                            ) ? (
                              <option value={batch.location}>{batch.location}</option>
                            ) : null}
                          </Select>
                        ) : (
                          <span className="font-mono text-xs text-slate-500">
                            {batch.location || "—"}
                          </span>
                        )}
                      </td>
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
                    On hand {formatQty(batch.qty_on_hand)} / received{" "}
                    {formatQty(batch.qty_received_total)} @ {formatMoney(batch.unit_cost)}
                  </p>
                  <p className="text-xs text-slate-500">
                    {batch.branch_name}
                    {batch.location ? ` · ${batch.location}` : ""}
                  </p>
                </li>
              ))}
            </ul>
            {data && data.count > 0 ? (
              <Pagination
                page={page}
                hasPrevious={Boolean(data.previous)}
                hasNext={Boolean(data.next)}
                onChange={setPage}
              />
            ) : null}
          </>
        )}
      </Card>
    </div>
  );
}
