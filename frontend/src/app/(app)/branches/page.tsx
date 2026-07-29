"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Branch, Paginated } from "@/lib/types";

const emptyForm = {
  code: "",
  name: "",
  type: "BRANCH" as "BRANCH" | "HEAD_OFFICE",
  phone: "",
  address: "",
};

export default function BranchesPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editing, setEditing] = useState<Branch | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["branches"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50"),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) => api.post<Branch>("/branches/", payload),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["branches"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) =>
      api.patch<Branch>(`/branches/${editing?.id}/`, payload),
    onSuccess: () => {
      setForm(emptyForm);
      setEditing(null);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["branches"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ branch, active }: { branch: Branch; active: boolean }) =>
      api.patch(`/branches/${branch.id}/`, { status: active ? "ACTIVE" : "INACTIVE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["branches"] }),
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate(form);
    } else {
      createMutation.mutate(form);
    }
  };

  const openEdit = (branch: Branch) => {
    setEditing(branch);
    setForm({
      code: branch.code,
      name: branch.name,
      type: branch.type,
      phone: branch.phone ?? "",
      address: branch.address ?? "",
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
        <h1 className="text-lg font-semibold text-slate-800">Branches</h1>
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
          {showForm ? "Close" : "Add branch"}
        </Button>
      </div>

      {showForm ? (
        <Card>
          <CardHeader
            title={editing ? `Edit ${editing.name}` : "New branch"}
            subtitle="Branches isolate stock, ledgers and document numbering."
          />
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
            <Field label="Type" error={fieldError("type")}>
              <Select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value as typeof form.type })}
              >
                <option value="BRANCH">Branch</option>
                <option value="HEAD_OFFICE">Head office</option>
              </Select>
            </Field>
            <Field label="Phone" error={fieldError("phone")}>
              <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <div className="col-span-2 lg:col-span-4">
              <Field label="Address" error={fieldError("address")}>
                <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
              </Field>
            </div>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {createMutation.isPending || updateMutation.isPending
                  ? "Saving…"
                  : editing
                    ? "Save changes"
                    : "Create branch"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="All branches" subtitle={data ? `${data.count} branch(es)` : undefined} />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No branches yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.results.map((branch) => (
              <li key={branch.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    {branch.name} <span className="font-mono text-xs text-slate-400">{branch.code}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {branch.type === "HEAD_OFFICE" ? "Head office" : "Branch"}
                    {branch.phone ? ` · ${branch.phone}` : ""}
                    {branch.address ? ` · ${branch.address}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={branch.status === "ACTIVE" ? "green" : "slate"}>{branch.status}</Badge>
                  <Button size="sm" variant="secondary" onClick={() => openEdit(branch)}>
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => statusMutation.mutate({ branch, active: branch.status !== "ACTIVE" })}
                    disabled={statusMutation.isPending}
                  >
                    {branch.status === "ACTIVE" ? "Deactivate" : "Activate"}
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
