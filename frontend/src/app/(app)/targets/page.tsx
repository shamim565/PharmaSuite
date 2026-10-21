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
import { ApiError, api } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { Branch, Paginated, Representative, SalesTarget } from "@/lib/types";

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function currentPeriod(): { fiscal_year: number; period_month: number } {
  const now = new Date();
  return { fiscal_year: now.getFullYear(), period_month: now.getMonth() + 1 };
}

function achievementTone(pct: number | null): "slate" | "green" | "amber" | "rose" {
  if (pct === null) return "slate";
  if (pct >= 100) return "green";
  if (pct >= 75) return "amber";
  return "rose";
}

const emptyForm = {
  representative: "",
  branch: "",
  target_amount: "",
  target_collection: "",
  target_visits: "0",
  notes: "",
};

export default function TargetsPage() {
  const { hasPerm } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [fiscalYear, setFiscalYear] = useState(currentPeriod().fiscal_year);
  const [periodMonth, setPeriodMonth] = useState(currentPeriod().period_month);

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<SalesTarget | null>(null);
  const [form, setForm] = useState(emptyForm);

  const params = new URLSearchParams({
    page_size: "50",
    page: String(page),
    fiscal_year: String(fiscalYear),
    period_month: String(periodMonth),
  });

  const targetsQuery = useQuery({
    queryKey: ["sales-targets", fiscalYear, periodMonth, page],
    queryFn: () => api.get<Paginated<SalesTarget>>(`/sales-targets/?${params.toString()}`),
  });
  const repsQuery = useQuery({
    queryKey: ["representatives", "select"],
    queryFn: () =>
      api.get<Paginated<Representative>>("/representatives/?page_size=200&is_active=true"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["sales-targets"] });
    queryClient.invalidateQueries({ queryKey: ["rep-performance"] });
  };

  const saveMutation = useMutation({
    meta: { successMessage: editing ? "Target updated" : "Target created" },
    mutationFn: () => {
      const body = {
        ...form,
        fiscal_year: fiscalYear,
        period_month: periodMonth,
        target_amount: form.target_amount || "0",
        target_collection: form.target_collection || "0",
        target_visits: Number(form.target_visits) || 0,
        branch: form.branch || null,
      };
      return editing
        ? api.patch<SalesTarget>(`/sales-targets/${editing.id}/`, body)
        : api.post<SalesTarget>("/sales-targets/", body);
    },
    onSuccess: () => {
      setEditing(null);
      setShowForm(false);
      setForm(emptyForm);
      invalidateAll();
    },
  });

  const deleteMutation = useMutation({
    meta: { successMessage: "Target deleted" },
    mutationFn: (id: string) => api.delete(`/sales-targets/${id}/`),
    onSuccess: invalidateAll,
  });

  const fieldError = (name: string): string | null => {
    const err = saveMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setShowForm(true);
  };

  const openEdit = (target: SalesTarget) => {
    setEditing(target);
    setForm({
      representative: target.representative,
      branch: target.branch ?? "",
      target_amount: target.target_amount,
      target_collection: target.target_collection,
      target_visits: String(target.target_visits),
      notes: target.notes,
    });
    setShowForm(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Sales targets</h1>
        {hasPerm("REP_MANAGE") ? (
          <Button size="sm" onClick={openCreate}>
            New target
          </Button>
        ) : null}
      </div>

      {/* Period filter */}
      <Card className="p-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="Fiscal year">
            <Input
              type="number"
              min={2000}
              max={2100}
              value={fiscalYear}
              onChange={(e) => {
                setFiscalYear(Number(e.target.value) || currentPeriod().fiscal_year);
                setPage(1);
              }}
            />
          </Field>
          <Field label="Month">
            <Select
              value={periodMonth}
              onChange={(e) => {
                setPeriodMonth(Number(e.target.value));
                setPage(1);
              }}
            >
              {MONTH_NAMES.map((name, index) => (
                <option key={index + 1} value={index + 1}>
                  {name}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      {/* Create / edit form */}
      {showForm && hasPerm("REP_MANAGE") ? (
        <Card>
          <CardHeader
            title={editing ? `Edit target — ${editing.representative_name}` : "New sales target"}
            subtitle={`FY ${fiscalYear} · ${MONTH_NAMES[periodMonth - 1]}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setShowForm(false)}>
                Close
              </Button>
            }
          />
            <form
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                saveMutation.mutate();
              }}
              className="space-y-3 p-4"
            >
              <ErrorBanner error={saveMutation.error} />
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Field label="Representative" error={fieldError("representative")}>
                  <Select
                    value={form.representative}
                    onChange={(e) => setForm({ ...form, representative: e.target.value })}
                    required
                  >
                    <option value="">Select…</option>
                    {repsQuery.data?.results.map((rep) => (
                      <option key={rep.id} value={rep.id}>
                        {rep.name} ({rep.code})
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Branch">
                  <Select
                    value={form.branch}
                    onChange={(e) => setForm({ ...form, branch: e.target.value })}
                  >
                    <option value="">All branches</option>
                    {branchesQuery.data?.results.map((branch) => (
                      <option key={branch.id} value={branch.id}>
                        {branch.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Sales target (৳)">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.target_amount}
                    onChange={(e) => setForm({ ...form, target_amount: e.target.value })}
                    required
                  />
                </Field>
                <Field label="Collection target (৳)">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.target_collection}
                    onChange={(e) => setForm({ ...form, target_collection: e.target.value })}
                  />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Field label="Visit target">
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    value={form.target_visits}
                    onChange={(e) => setForm({ ...form, target_visits: e.target.value })}
                  />
                </Field>
                <div className="col-span-2">
                  <Field label="Notes">
                    <Input
                      value={form.notes}
                      onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    />
                  </Field>
                </div>
              </div>
              <Button type="submit" className="w-full lg:w-auto" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Saving…" : editing ? "Save changes" : "Create target"}
              </Button>
            </form>
          </Card>
      ) : null}

      <Card>
        <CardHeader
          title={`Targets — ${MONTH_NAMES[periodMonth - 1]} ${fiscalYear}`}
          subtitle={targetsQuery.data ? `${targetsQuery.data.count} target(s)` : undefined}
        />
        <ErrorBanner error={targetsQuery.error} />
        {targetsQuery.isLoading ? (
          <Spinner />
        ) : !targetsQuery.data || targetsQuery.data.results.length === 0 ? (
          <EmptyState
            message="No targets for this period."
            action={
              hasPerm("REP_MANAGE") ? (
                <Button size="sm" onClick={openCreate}>
                  Create the first target
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y divide-slate-100">
            {targetsQuery.data.results.map((target) => {
              const pct = target.achieved_percent;
              return (
                <li key={target.id} className="space-y-2 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium">
                        {target.representative_name}{" "}
                        <span className="font-mono text-xs text-slate-500">
                          {target.representative_code}
                        </span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {target.branch_name || "All branches"} · visits target{" "}
                        {target.target_visits}
                        {target.notes ? ` · ${target.notes}` : null}
                      </p>
                    </div>
                    <Badge tone={achievementTone(pct)}>
                      {pct === null ? "No target data" : `${pct}% achieved`}
                    </Badge>
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>
                        Sales {formatMoney(target.achieved_sales)} of{" "}
                        {formatMoney(target.target_amount)}
                      </span>
                      <span>Collection {formatMoney(target.target_collection)}</span>
                    </div>
                    <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full ${
                          pct === null
                            ? "bg-slate-300"
                            : pct >= 100
                              ? "bg-primary-600"
                              : pct >= 75
                                ? "bg-amber-500"
                                : "bg-danger-500"
                        }`}
                        style={{ width: `${Math.min(pct ?? 0, 100)}%` }}
                      />
                    </div>
                  </div>
                  {hasPerm("REP_MANAGE") ? (
                    <div className="flex gap-2">
                      <Button size="sm" variant="secondary" onClick={() => openEdit(target)}>
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => deleteMutation.mutate(target.id)}
                        disabled={deleteMutation.isPending}
                      >
                        Delete
                      </Button>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
        {targetsQuery.data && targetsQuery.data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(targetsQuery.data.previous)}
            hasNext={Boolean(targetsQuery.data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
