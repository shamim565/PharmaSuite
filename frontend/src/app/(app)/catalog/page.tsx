"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Paginated } from "@/lib/types";

type MasterRow = {
  id: string;
  name: string;
  is_active: boolean;
  [key: string]: unknown;
};

type TextField = { name: string; label: string; type?: "text" | "number" };
type SelectField = { name: string; label: string; options: { value: string; label: string }[] };

function MasterSection({
  title,
  subtitle,
  endpoint,
  queryKey,
  textFields,
  selectField,
}: {
  title: string;
  subtitle: string;
  endpoint: string;
  queryKey: string;
  textFields: TextField[];
  selectField?: SelectField;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>(
    Object.fromEntries(textFields.map((f) => [f.name, ""]).concat(selectField ? [[selectField.name, selectField.options[0]?.value ?? ""]] : [])),
  );

  const { data, isLoading, error } = useQuery({
    queryKey: [queryKey],
    queryFn: () => api.get<Paginated<MasterRow>>(`${endpoint}?page_size=200`),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post(endpoint, {
        ...form,
        ...(selectField ? {} : {}),
      }),
    onSuccess: () => {
      setForm(Object.fromEntries(textFields.map((f) => [f.name, ""]).concat(selectField ? [[selectField.name, selectField.options[0]?.value ?? ""]] : [])));
      queryClient.invalidateQueries({ queryKey: [queryKey] });
      queryClient.invalidateQueries({ queryKey: [queryKey, "select"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (row: MasterRow) => api.patch(`${endpoint}/${row.id}/`, { is_active: !row.is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [queryKey] });
      queryClient.invalidateQueries({ queryKey: [queryKey, "select"] });
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate();
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  return (
    <Card>
      <CardHeader title={title} subtitle={subtitle} />
      <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 border-b border-slate-100 p-4 lg:grid-cols-4">
        <div className="col-span-2 lg:col-span-4">
          <ErrorBanner error={createMutation.error} />
        </div>
        {textFields.map((field) => (
          <Field key={field.name} label={field.label} error={fieldError(field.name)}>
            <Input
              type={field.type ?? "text"}
              value={form[field.name] ?? ""}
              onChange={(e) => setForm({ ...form, [field.name]: e.target.value })}
              required={field.name === "name"}
            />
          </Field>
        ))}
        {selectField ? (
          <Field label={selectField.label} error={fieldError(selectField.name)}>
            <Select
              value={form[selectField.name] ?? ""}
              onChange={(e) => setForm({ ...form, [selectField.name]: e.target.value })}
            >
              {selectField.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}
        <div className="col-span-2 flex items-end lg:col-span-4">
          <Button type="submit" size="sm" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Saving…" : `Add ${title.slice(0, -1).toLowerCase()}`}
          </Button>
        </div>
      </form>
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : !data || data.results.length === 0 ? (
        <EmptyState message="Nothing here yet." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {data.results.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <div className="text-sm">
                <span className="font-medium">{row.name}</span>
                {typeof row.parent_name === "string" && row.parent_name ? (
                  <span className="text-xs text-slate-500"> · parent: {row.parent_name}</span>
                ) : null}
                {typeof row.therapeutic_class === "string" && row.therapeutic_class ? (
                  <span className="text-xs text-slate-500"> · {row.therapeutic_class}</span>
                ) : null}
                {typeof row.country === "string" && row.country ? (
                  <span className="text-xs text-slate-500"> · {row.country}</span>
                ) : null}
                {typeof row.unit_type === "string" ? (
                  <span className="text-xs text-slate-500"> · {row.unit_type}</span>
                ) : null}
                {typeof row.symbol === "string" && row.symbol ? (
                  <span className="text-xs text-slate-500"> · {row.symbol}</span>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                {row.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => toggleMutation.mutate(row)}
                  disabled={toggleMutation.isPending}
                >
                  {row.is_active ? "Deactivate" : "Activate"}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const TABS = ["Generics", "Manufacturers", "Categories", "Units"] as const;
type Tab = (typeof TABS)[number];

export default function CatalogPage() {
  const [tab, setTab] = useState<Tab>("Generics");

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-800">Catalog masters</h1>

      <div className="flex flex-wrap gap-2">
        {TABS.map((item) => (
          <button
            key={item}
            onClick={() => setTab(item)}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
              tab === item ? "bg-emerald-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {tab === "Generics" ? (
        <MasterSection
          title="Generics"
          subtitle="Active pharmaceutical ingredient groups."
          endpoint="/generics/"
          queryKey="generics"
          textFields={[
            { name: "name", label: "Name" },
            { name: "therapeutic_class", label: "Therapeutic class" },
          ]}
        />
      ) : null}

      {tab === "Manufacturers" ? (
        <MasterSection
          title="Manufacturers"
          subtitle="Companies supplying or producing medicines."
          endpoint="/manufacturers/"
          queryKey="manufacturers"
          textFields={[
            { name: "name", label: "Name" },
            { name: "country", label: "Country" },
          ]}
        />
      ) : null}

      {tab === "Categories" ? (
        <MasterSection
          title="Categories"
          subtitle="Therapeutic or commercial groupings."
          endpoint="/medicine-categories/"
          queryKey="categories"
          textFields={[
            { name: "name", label: "Name" },
            { name: "sort_order", label: "Sort order", type: "number" },
          ]}
        />
      ) : null}

      {tab === "Units" ? (
        <MasterSection
          title="Units"
          subtitle="Base and pack units used by stock movements."
          endpoint="/units/"
          queryKey="units"
          textFields={[
            { name: "name", label: "Name" },
            { name: "symbol", label: "Symbol" },
          ]}
          selectField={{
            name: "unit_type",
            label: "Type",
            options: [
              { value: "COUNT", label: "Count" },
              { value: "WEIGHT", label: "Weight" },
              { value: "VOLUME", label: "Volume" },
            ],
          }}
        />
      ) : null}
    </div>
  );
}
