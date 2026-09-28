"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Badge, Button, Card, CardHeader, ConfirmButton, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Branch, Paginated, Role, UserRecord } from "@/lib/types";

const emptyForm = {
  full_name: "",
  mobile: "",
  email: "",
  password: "",
  role_ids: [] as string[],
  branch_ids: [] as string[],
  default_branch_id: "",
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editing, setEditing] = useState<UserRecord | null>(null);

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<Paginated<UserRecord>>("/users/?page_size=50"),
  });
  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Paginated<Role>>("/roles/?page_size=50"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50"),
  });

  const createMutation = useMutation({
    meta: { successMessage: "User created" },
    mutationFn: (payload: typeof emptyForm) =>
      api.post<UserRecord>("/users/", {
        ...payload,
        email: payload.email || null,
        default_branch_id: payload.default_branch_id || null,
      }),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const updateMutation = useMutation({
    meta: { successMessage: "User updated" },
    mutationFn: (payload: typeof emptyForm) =>
      api.patch<UserRecord>(`/users/${editing?.id}/`, {
        full_name: payload.full_name,
        email: payload.email || null,
        role_ids: payload.role_ids,
        branch_ids: payload.branch_ids,
        default_branch_id: payload.default_branch_id || null,
      }),
    onSuccess: () => {
      setForm(emptyForm);
      setEditing(null);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const openEdit = (user: UserRecord) => {
    setEditing(user);
    setForm({
      full_name: user.full_name,
      mobile: user.mobile,
      email: user.email ?? "",
      password: "",
      role_ids: user.roles.map((role) => role.id),
      branch_ids: user.branches.map((branch) => branch.id),
      default_branch_id: user.branches.find((branch) => branch.is_default)?.id ?? "",
    });
    setShowForm(true);
  };

  const statusMutation = useMutation({
    meta: { successMessage: "User status updated" },
    mutationFn: ({ user, activate }: { user: UserRecord; activate: boolean }) =>
      api.post(`/users/${user.id}/${activate ? "activate" : "deactivate"}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const reset2faMutation = useMutation({
    meta: { successMessage: "2FA reset" },
    mutationFn: (user: UserRecord) => api.post(`/users/${user.id}/reset-2fa/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate(form);
    } else {
      createMutation.mutate(form);
    }
  };

  const fieldError = (name: string): string | null => {
    const err = updateMutation.error ?? createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  const toggleSelection = (key: "role_ids" | "branch_ids", value: string) => {
    setForm((prev) => {
      const selected = prev[key].includes(value)
        ? prev[key].filter((v) => v !== value)
        : [...prev[key], value];
      return { ...prev, [key]: selected };
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Users</h1>
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
          {showForm ? "Close" : "Add user"}
        </Button>
      </div>

      {showForm ? (
        <Card>
          <CardHeader title={editing ? `Edit ${editing.full_name}` : "New user"} subtitle="Assign a role and at least one branch." />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error ?? updateMutation.error} />
            </div>
            <Field label="Full name" error={fieldError("full_name")}>
              <Input
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required
              />
            </Field>
            <Field label="Mobile" error={fieldError("mobile")}>
              <Input
                value={form.mobile}
                onChange={(e) => setForm({ ...form, mobile: e.target.value })}
                disabled={Boolean(editing)}
                required
              />
            </Field>
            <Field label="Email (optional)" error={fieldError("email")}>
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </Field>
            {!editing ? (
              <Field label="Temporary password" error={fieldError("password")}>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  minLength={8}
                  required
                />
              </Field>
            ) : null}

            <div className="col-span-2 space-y-1 lg:col-span-2">
              <span className="text-xs font-medium text-slate-600">Roles</span>
              <div className="flex flex-wrap gap-2 rounded-lg border border-slate-200 p-2">
                {rolesQuery.data?.results.map((role) => (
                  <label key={role.id} className="flex items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={form.role_ids.includes(role.id)}
                      onChange={() => toggleSelection("role_ids", role.id)}
                    />
                    {role.name}
                  </label>
                ))}
                {rolesQuery.isLoading ? <span className="text-xs text-slate-500">Loading…</span> : null}
              </div>
              {fieldError("role_ids") ? (
                <span className="text-xs text-danger-600">{fieldError("role_ids")}</span>
              ) : null}
            </div>

            <div className="col-span-2 space-y-1 lg:col-span-2">
              <span className="text-xs font-medium text-slate-600">Branches</span>
              <div className="flex flex-wrap gap-2 rounded-lg border border-slate-200 p-2">
                {branchesQuery.data?.results.map((branch) => (
                  <label key={branch.id} className="flex items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={form.branch_ids.includes(branch.id)}
                      onChange={() => toggleSelection("branch_ids", branch.id)}
                    />
                    {branch.name}
                  </label>
                ))}
                {branchesQuery.isLoading ? <span className="text-xs text-slate-500">Loading…</span> : null}
              </div>
              {fieldError("branch_ids") ? (
                <span className="text-xs text-danger-600">{fieldError("branch_ids")}</span>
              ) : null}
            </div>

            <Field label="Default branch" error={fieldError("default_branch_id")}>
              <Select
                value={form.default_branch_id}
                onChange={(e) => setForm({ ...form, default_branch_id: e.target.value })}
              >
                <option value="">—</option>
                {branchesQuery.data?.results
                  .filter((b) => form.branch_ids.includes(b.id))
                  .map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
              </Select>
            </Field>

            <div className="col-span-2 flex items-end lg:col-span-3">
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {createMutation.isPending || updateMutation.isPending
                  ? "Saving…"
                  : editing
                    ? "Save changes"
                    : "Create user"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Team" subtitle={usersQuery.data ? `${usersQuery.data.count} user(s)` : undefined} />
        <ErrorBanner error={usersQuery.error} />
        {usersQuery.isLoading ? (
          <Spinner />
        ) : !usersQuery.data || usersQuery.data.results.length === 0 ? (
          <EmptyState message="No users found." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {usersQuery.data.results.map((user) => (
              <li key={user.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    {user.full_name}{" "}
                    {user.is_superuser ? <Badge tone="blue">Owner</Badge> : null}
                  </p>
                  <p className="text-xs text-slate-500">
                    {user.mobile}
                    {user.email ? ` · ${user.email}` : ""} ·{" "}
                    {user.roles.map((r) => r.name).join(", ") || "no role"}
                  </p>
                  <p className="text-xs text-slate-500">
                    Branches: {user.branches.map((b) => b.code).join(", ") || "—"}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {user.status === "ACTIVE" ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                  {user.totp_enabled ? <Badge tone="blue">2FA</Badge> : null}
                  <Button size="sm" variant="secondary" onClick={() => openEdit(user)}>
                    Edit
                  </Button>
                  {user.status === "ACTIVE" ? (
                    <ConfirmButton
                      size="sm"
                      variant="secondary"
                      confirmLabel="Deactivate?"
                      onConfirm={() => statusMutation.mutate({ user, activate: false })}
                      disabled={statusMutation.isPending}
                    >
                      Deactivate
                    </ConfirmButton>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => statusMutation.mutate({ user, activate: true })}
                      disabled={statusMutation.isPending}
                    >
                      Activate
                    </Button>
                  )}
                  {user.totp_enabled ? (
                    <ConfirmButton
                      size="sm"
                      variant="ghost"
                      confirmLabel="Reset 2FA?"
                      onConfirm={() => reset2faMutation.mutate(user)}
                      disabled={reset2faMutation.isPending}
                    >
                      Reset 2FA
                    </ConfirmButton>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
