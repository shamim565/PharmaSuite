"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";

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
  Select,
  Spinner,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Paginated, PermissionCatalog, PermissionItem, Role } from "@/lib/types";

type Effect = "ALLOW" | "DENY";

const emptyForm = { code: "", name: "", description: "", branch_scope: "ASSIGNED" };

function moduleLabel(module: string): string {
  return module.replace(/_/g, " ");
}

export default function RolesPage() {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const canView = hasPerm("ROLE_VIEW") || hasPerm("ROLE_MANAGE");
  const canManage = hasPerm("ROLE_MANAGE");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [effects, setEffects] = useState<Record<string, Effect>>({});
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [meta, setMeta] = useState({ name: "", description: "", branch_scope: "ASSIGNED" });

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Paginated<Role>>("/roles/?page_size=100"),
    enabled: canView,
  });
  const catalogQuery = useQuery({
    queryKey: ["permissions", "catalog"],
    queryFn: () => api.get<PermissionCatalog>("/permissions/"),
    enabled: canView,
  });
  const roleQuery = useQuery({
    queryKey: ["roles", selectedId],
    queryFn: () => api.get<Role>(`/roles/${selectedId}/`),
    enabled: Boolean(selectedId),
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!selectedId && rolesQuery.data?.results.length) {
      setSelectedId(rolesQuery.data.results[0].id);
    }
  }, [rolesQuery.data, selectedId]);

  useEffect(() => {
    const role = roleQuery.data;
    if (!role) return;
    const map: Record<string, Effect> = {};
    (role.permissions ?? []).forEach((entry) => {
      map[entry.code] = entry.effect === "DENY" ? "DENY" : "ALLOW";
    });
    setEffects(map);
    setMeta({
      name: role.name,
      description: role.description ?? "",
      branch_scope: role.branch_scope ?? "ASSIGNED",
    });
    setDirty(false);
    setMessage("");
  }, [roleQuery.data]);

  const createMutation = useMutation({
    meta: { successMessage: "Role created" },
    mutationFn: () => api.post<Role>("/roles/", form),
    onSuccess: (role) => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setSelectedId(role.id);
      setMessage("Role created. Grant permissions below.");
    },
  });

  const detailsMutation = useMutation({
    meta: { successMessage: "Role details saved" },
    mutationFn: () => api.patch<Role>(`/roles/${selectedId}/`, meta),
    onSuccess: (role) => {
      queryClient.setQueryData(["roles", selectedId], role);
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setMessage("Role details saved.");
    },
  });

  const permissionsMutation = useMutation({
    meta: { successMessage: "Permissions saved" },
    mutationFn: () =>
      api.put<Role>(`/roles/${selectedId}/permissions/`, {
        permissions: Object.entries(effects).map(([code, effect]) => ({ code, effect })),
      }),
    onSuccess: (role) => {
      queryClient.setQueryData(["roles", selectedId], role);
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setDirty(false);
      setMessage("Permissions saved.");
    },
  });

  const setEffect = (code: string, effect: Effect | null) => {
    setEffects((current) => {
      const next = { ...current };
      if (effect) next[code] = effect;
      else delete next[code];
      return next;
    });
    setDirty(true);
    setMessage("");
  };

  const applyModule = (items: PermissionItem[], effect: Effect) => {
    setEffects((current) => {
      const next = { ...current };
      items.forEach((item) => {
        next[item.code] = effect;
      });
      return next;
    });
    setDirty(true);
    setMessage("");
  };

  const clearModule = (items: PermissionItem[]) => {
    setEffects((current) => {
      const next = { ...current };
      items.forEach((item) => {
        delete next[item.code];
      });
      return next;
    });
    setDirty(true);
    setMessage("");
  };

  const onCreate = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate();
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  if (!canView) {
    return (
      <Card>
        <EmptyState message="You need ROLE_VIEW or ROLE_MANAGE to manage roles." />
      </Card>
    );
  }

  const catalog = catalogQuery.data ?? {};
  const allowedCount = Object.values(effects).filter((effect) => effect === "ALLOW").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Roles & permissions</h1>
        {canManage ? (
          <Button size="sm" onClick={() => setShowForm((value) => !value)}>
            {showForm ? "Close" : "New role"}
          </Button>
        ) : null}
      </div>

      {showForm && canManage ? (
        <Card>
          <CardHeader
            title="New role"
            subtitle="Create the role first, then grant permissions from the matrix."
          />
          <form onSubmit={onCreate} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error} />
            </div>
            <Field label="Code" error={fieldError("code")}>
              <Input
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
                placeholder="STORE_KEEPER"
                required
              />
            </Field>
            <Field label="Name" error={fieldError("name")}>
              <Input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
            </Field>
            <Field label="Branch scope">
              <Select
                value={form.branch_scope}
                onChange={(event) => setForm({ ...form, branch_scope: event.target.value })}
              >
                <option value="ASSIGNED">Assigned branches</option>
                <option value="ALL">All branches</option>
              </Select>
            </Field>
            <Field label="Description" error={fieldError("description")}>
              <Input
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </Field>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Create role"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <Card>
          <CardHeader
            title="Roles"
            subtitle={rolesQuery.data ? `${rolesQuery.data.count} role(s)` : undefined}
          />
          <ErrorBanner error={rolesQuery.error} />
          {rolesQuery.isLoading ? (
            <Spinner />
          ) : !rolesQuery.data?.results.length ? (
            <EmptyState message="No roles defined." />
          ) : (
            <ul className="max-h-[70vh] divide-y divide-slate-100 overflow-auto">
              {rolesQuery.data.results.map((role) => (
                <li key={role.id}>
                  <button
                    onClick={() => setSelectedId(role.id)}
                    className={`w-full px-4 py-3 text-left transition ${
                      role.id === selectedId ? "bg-primary-50" : "hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-slate-700">{role.name}</p>
                      {role.is_system ? <Badge tone="blue">system</Badge> : null}
                    </div>
                    <p className="font-mono text-[11px] text-slate-500">{role.code}</p>
                    <p className="text-[11px] text-slate-500">
                      {role.branch_scope === "ALL" ? "All branches" : "Assigned branches"}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-4">
          {message ? (
            <div className="rounded-lg border border-primary-200 bg-primary-50 px-3 py-2 text-sm text-primary-700">
              {message}
            </div>
          ) : null}

          {!selectedId || roleQuery.isLoading ? (
            <Card>
              <Spinner label="Select a role…" />
            </Card>
          ) : roleQuery.error ? (
            <Card>
              <ErrorBanner error={roleQuery.error} />
            </Card>
          ) : roleQuery.data ? (
            <>
              <Card>
                <CardHeader
                  title={`Role details — ${roleQuery.data.name}`}
                  subtitle={roleQuery.data.code}
                />
                <div className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
                  <div className="col-span-2 lg:col-span-4">
                    <ErrorBanner error={detailsMutation.error} />
                  </div>
                  <div className="col-span-2">
                    <Field label="Name">
                      <Input
                        value={meta.name}
                        disabled={!canManage}
                        onChange={(event) => setMeta({ ...meta, name: event.target.value })}
                      />
                    </Field>
                  </div>
                  <Field label="Branch scope">
                    <Select
                      value={meta.branch_scope}
                      disabled={!canManage}
                      onChange={(event) => setMeta({ ...meta, branch_scope: event.target.value })}
                    >
                      <option value="ASSIGNED">Assigned branches</option>
                      <option value="ALL">All branches</option>
                    </Select>
                  </Field>
                  <Field label="Description">
                    <Input
                      value={meta.description}
                      disabled={!canManage}
                      onChange={(event) => setMeta({ ...meta, description: event.target.value })}
                    />
                  </Field>
                  {canManage ? (
                    <div className="col-span-2 lg:col-span-4">
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={detailsMutation.isPending}
                        onClick={() => detailsMutation.mutate()}
                      >
                        Save details
                      </Button>
                    </div>
                  ) : null}
                </div>
              </Card>

              <Card>
                <CardHeader
                  title="Permissions"
                  subtitle={`${allowedCount} allowed · ${dirty ? "unsaved changes" : "saved"}`}
                  action={
                    canManage ? (
                      <Button
                        size="sm"
                        disabled={!dirty || permissionsMutation.isPending}
                        onClick={() => permissionsMutation.mutate()}
                      >
                        {permissionsMutation.isPending ? "Saving…" : "Save permissions"}
                      </Button>
                    ) : undefined
                  }
                />
                <div className="border-b border-slate-100 px-4 py-3">
                  <ErrorBanner error={permissionsMutation.error} />
                  {roleQuery.data.is_system ? (
                    <p className="mt-2 text-xs text-slate-500">
                      System role — edits are kept; rerunning{" "}
                      <code>seed_rbac --sync-permissions</code> restores the built-in defaults.
                    </p>
                  ) : null}
                </div>
                {catalogQuery.isLoading ? (
                  <Spinner />
                ) : (
                  <div>
                    {Object.entries(catalog)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([module, items]) => (
                        <div key={module} className="border-b border-slate-100 last:border-0">
                          <div className="flex items-center justify-between bg-slate-50 px-4 py-2">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              {moduleLabel(module)}
                            </p>
                            {canManage ? (
                              <div className="flex gap-3">
                                <button
                                  type="button"
                                  className="text-xs text-primary-700 hover:underline"
                                  onClick={() => applyModule(items, "ALLOW")}
                                >
                                  Allow all
                                </button>
                                <button
                                  type="button"
                                  className="text-xs text-slate-500 hover:underline"
                                  onClick={() => clearModule(items)}
                                >
                                  Clear
                                </button>
                              </div>
                            ) : null}
                          </div>
                          <ul className="divide-y divide-slate-100">
                            {items.map((permission) => {
                              const effect = effects[permission.code];
                              return (
                                <li
                                  key={permission.code}
                                  className="flex flex-wrap items-center justify-between gap-2 px-4 py-2"
                                >
                                  <div>
                                    <p className="text-sm text-slate-700">
                                      {permission.label}{" "}
                                      {permission.is_sensitive ? (
                                        <Badge tone="amber">sensitive</Badge>
                                      ) : null}
                                    </p>
                                    <p className="font-mono text-[11px] text-slate-500">
                                      {permission.code}
                                    </p>
                                  </div>
                                  {canManage ? (
                                    <div className="flex overflow-hidden rounded-lg border border-slate-200 text-xs">
                                      <button
                                        type="button"
                                        onClick={() => setEffect(permission.code, null)}
                                        className={`px-2.5 py-1 ${
                                          effect === undefined
                                            ? "bg-slate-700 text-white"
                                            : "bg-white text-slate-500 hover:bg-slate-50"
                                        }`}
                                      >
                                        Default
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => setEffect(permission.code, "ALLOW")}
                                        className={`px-2.5 py-1 ${
                                          effect === "ALLOW"
                                            ? "bg-primary-600 text-white"
                                            : "bg-white text-slate-500 hover:bg-slate-50"
                                        }`}
                                      >
                                        Allow
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => setEffect(permission.code, "DENY")}
                                        className={`px-2.5 py-1 ${
                                          effect === "DENY"
                                            ? "bg-danger-600 text-white"
                                            : "bg-white text-slate-500 hover:bg-slate-50"
                                        }`}
                                      >
                                        Deny
                                      </button>
                                    </div>
                                  ) : (
                                    <Badge
                                      tone={
                                        effect === "ALLOW"
                                          ? "green"
                                          : effect === "DENY"
                                            ? "rose"
                                            : "slate"
                                      }
                                    >
                                      {effect ? effect.toLowerCase() : "default"}
                                    </Badge>
                                  )}
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      ))}
                  </div>
                )}
              </Card>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
