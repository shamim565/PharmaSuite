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
  Pagination,
  Select,
  Spinner,
  Tabs,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type {
  Branch,
  Customer,
  Doctor,
  Paginated,
  RepPerformanceReport,
  Representative,
  RepresentativeAssignment,
  Territory,
} from "@/lib/types";

const TABS = ["Representatives", "Territories"] as const;
type Tab = (typeof TABS)[number];

const emptyRep = {
  code: "",
  name: "",
  rep_type: "SALES",
  phone: "",
  branch: "",
};

const emptyTerritory = {
  name: "",
  territory_type: "AREA",
  parent: "",
};

function RepPerformanceCard({ repId }: { repId: string }) {
  const now = new Date();
  const [fiscalYear, setFiscalYear] = useState(now.getFullYear());
  const [periodMonth, setPeriodMonth] = useState(now.getMonth() + 1);

  const { data, isLoading, error } = useQuery({
    queryKey: ["rep-performance", repId, fiscalYear, periodMonth],
    queryFn: () =>
      api.get<RepPerformanceReport>(
        `/reports/rep-performance/?representative=${repId}&fiscal_year=${fiscalYear}&period_month=${periodMonth}`,
      ),
  });

  const row = data?.results[0];
  const pct = row?.achievement_pct ?? null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase text-slate-500">Target vs actual (sales)</p>
        <div className="flex gap-2">
          <Select
            value={fiscalYear}
            onChange={(e) => setFiscalYear(Number(e.target.value))}
            className="w-28"
            aria-label="Fiscal year"
          >
            {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((year) => (
              <option key={year} value={year}>
                FY {year}
              </option>
            ))}
          </Select>
          <Select
            value={periodMonth}
            onChange={(e) => setPeriodMonth(Number(e.target.value))}
            className="w-36"
            aria-label="Month"
          >
            {Array.from({ length: 12 }, (_, i) => (
              <option key={i + 1} value={i + 1}>
                {new Date(2020, i, 1).toLocaleDateString("en-GB", { month: "long" })}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : !row ? (
        <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
          No target or sales recorded for this period.
        </p>
      ) : (
        <div className="space-y-2 rounded-lg border border-slate-200 p-3">
          <div className="flex items-center justify-between text-sm">
            <span>
              {formatMoney(row.actual_sales)}{" "}
              <span className="text-xs text-slate-500">of {formatMoney(row.target_amount)}</span>
            </span>
            {pct === null ? (
              <Badge tone="slate">No target</Badge>
            ) : (
              <Badge tone={pct >= 100 ? "green" : pct >= 75 ? "amber" : "rose"}>{pct}%</Badge>
            )}
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
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
      )}
    </div>
  );
}

function RepPanel({ rep, onClose }: { rep: Representative; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [entityType, setEntityType] = useState<"CUSTOMER" | "DOCTOR" | "TERRITORY">("CUSTOMER");
  const [entityId, setEntityId] = useState("");

  const assignmentsQuery = useQuery({
    queryKey: ["rep-assignments", rep.id],
    queryFn: () => api.get<RepresentativeAssignment[]>(`/representatives/${rep.id}/assignments/`),
  });
  const customersQuery = useQuery({
    queryKey: ["customers", "select"],
    queryFn: () => api.get<Paginated<Customer>>("/customers/?page_size=200&is_active=true"),
    enabled: entityType === "CUSTOMER",
  });
  const doctorsQuery = useQuery({
    queryKey: ["doctors", "select"],
    queryFn: () => api.get<Paginated<Doctor>>("/doctors/?page_size=200&is_active=true"),
    enabled: entityType === "DOCTOR",
  });
  const territoriesQuery = useQuery({
    queryKey: ["territories", "select"],
    queryFn: () => api.get<Paginated<Territory>>("/territories/?page_size=100&is_active=true"),
    enabled: entityType === "TERRITORY",
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["rep-assignments", rep.id] });
    queryClient.invalidateQueries({ queryKey: ["representatives"] });
  };

  const assignMutation = useMutation({
    meta: { successMessage: "Assignment added" },
    mutationFn: () =>
      api.post(`/representatives/${rep.id}/assign/`, {
        entity_type: entityType,
        entity_id: entityId,
      }),
    onSuccess: () => {
      setEntityId("");
      invalidate();
    },
  });
  const unassignMutation = useMutation({
    meta: { successMessage: "Assignment removed" },
    mutationFn: (assignment: RepresentativeAssignment) =>
      api.post(`/representatives/${rep.id}/unassign/`, {
        entity_type: assignment.entity_type,
        entity_id: assignment.entity_id,
      }),
    onSuccess: () => invalidate(),
  });

  const options = (() => {
    if (entityType === "CUSTOMER")
      return (customersQuery.data?.results ?? []).map((c) => ({ id: c.id, label: c.name }));
    if (entityType === "DOCTOR")
      return (doctorsQuery.data?.results ?? []).map((d) => ({ id: d.id, label: d.name }));
    return (territoriesQuery.data?.results ?? []).map((t) => ({ id: t.id, label: t.name }));
  })();

  return (
    <Card>
      <CardHeader
        title={`${rep.name} (${rep.code})`}
        subtitle={`${rep.rep_type === "MEDICAL" ? "Medical representative" : "Sales representative"}${rep.branch_name ? ` · ${rep.branch_name}` : ""}`}
        action={
          <Button size="sm" variant="secondary" onClick={onClose}>
            Close
          </Button>
        }
      />
      <div className="space-y-3 p-4">
        <p className="text-xs font-semibold uppercase text-slate-500">Current assignments</p>
        <ErrorBanner error={assignMutation.error} />
        {assignmentsQuery.isLoading ? (
          <Spinner />
        ) : !assignmentsQuery.data || assignmentsQuery.data.length === 0 ? (
          <EmptyState message="No assignments yet." />
        ) : (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {assignmentsQuery.data.map((assignment) => (
              <li
                key={assignment.id}
                className="flex items-center justify-between px-3 py-2 text-sm"
              >
                <div>
                  <p className="font-medium">{assignment.entity_label}</p>
                  <p className="text-xs text-slate-500">
                    {assignment.entity_type} · since {formatDate(assignment.effective_from)}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => unassignMutation.mutate(assignment)}
                >
                  Unassign
                </Button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-end gap-2">
          <div className="w-40">
            <Field label="Type">
              <Select
                value={entityType}
                onChange={(e) => {
                  setEntityType(e.target.value as typeof entityType);
                  setEntityId("");
                }}
              >
                <option value="CUSTOMER">Customer</option>
                <option value="DOCTOR">Doctor</option>
                <option value="TERRITORY">Territory</option>
              </Select>
            </Field>
          </div>
          <div className="w-64">
            <Field label="Target">
              <Select value={entityId} onChange={(e) => setEntityId(e.target.value)}>
                <option value="">Select…</option>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Button
            size="sm"
            onClick={() => assignMutation.mutate()}
            disabled={!entityId || assignMutation.isPending}
          >
            Assign
          </Button>
        </div>

        <RepPerformanceCard repId={rep.id} />
      </div>
    </Card>
  );
}

export default function RepsPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("Representatives");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showRepForm, setShowRepForm] = useState(false);
  const [showTerritoryForm, setShowTerritoryForm] = useState(false);
  const [repForm, setRepForm] = useState(emptyRep);
  const [territoryForm, setTerritoryForm] = useState(emptyTerritory);
  const [selected, setSelected] = useState<Representative | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  const repParams = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) repParams.set("search", debouncedSearch);

  const repsQuery = useQuery({
    queryKey: ["representatives", debouncedSearch, page],
    queryFn: () => api.get<Paginated<Representative>>(`/representatives/?${repParams.toString()}`),
  });
  const territoriesQuery = useQuery({
    queryKey: ["territories", "list"],
    queryFn: () => api.get<Paginated<Territory>>("/territories/?page_size=100"),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=50&status=ACTIVE"),
  });

  const repMutation = useMutation({
    meta: { successMessage: "Representative created" },
    mutationFn: (payload: typeof emptyRep) =>
      api.post<Representative>("/representatives/", { ...payload, branch: payload.branch || null }),
    onSuccess: () => {
      setRepForm(emptyRep);
      setShowRepForm(false);
      queryClient.invalidateQueries({ queryKey: ["representatives"] });
    },
  });
  const territoryMutation = useMutation({
    meta: { successMessage: "Territory created" },
    mutationFn: (payload: typeof emptyTerritory) =>
      api.post<Territory>("/territories/", { ...payload, parent: payload.parent || null }),
    onSuccess: () => {
      setTerritoryForm(emptyTerritory);
      setShowTerritoryForm(false);
      queryClient.invalidateQueries({ queryKey: ["territories"] });
    },
  });

  const fieldError = (error: unknown, name: string): string | null => {
    if (error instanceof ApiError && error.fieldErrors?.[name]) return error.fieldErrors[name][0];
    return null;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Field team</h1>
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="Search name, phone…"
            aria-label="Search representatives"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-48"
          />
          {tab === "Representatives" ? (
            <Button size="sm" onClick={() => setShowRepForm((v) => !v)}>
              {showRepForm ? "Close" : "Add representative"}
            </Button>
          ) : (
            <Button size="sm" onClick={() => setShowTerritoryForm((v) => !v)}>
              {showTerritoryForm ? "Close" : "Add territory"}
            </Button>
          )}
        </div>
      </div>

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "Representatives" ? (
        <>
          {selected ? <RepPanel rep={selected} onClose={() => setSelected(null)} /> : null}
          {showRepForm ? (
            <Card>
              <CardHeader title="New representative" />
              <form
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  repMutation.mutate(repForm);
                }}
                className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4"
              >
                <div className="col-span-2 lg:col-span-4">
                  <ErrorBanner error={repMutation.error} />
                </div>
                <Field label="Code" error={fieldError(repMutation.error, "code")}>
                  <Input
                    value={repForm.code}
                    onChange={(e) => setRepForm({ ...repForm, code: e.target.value })}
                    required
                  />
                </Field>
                <Field label="Name" error={fieldError(repMutation.error, "name")}>
                  <Input
                    value={repForm.name}
                    onChange={(e) => setRepForm({ ...repForm, name: e.target.value })}
                    required
                  />
                </Field>
                <Field label="Type" error={fieldError(repMutation.error, "rep_type")}>
                  <Select
                    value={repForm.rep_type}
                    onChange={(e) => setRepForm({ ...repForm, rep_type: e.target.value })}
                  >
                    <option value="SALES">Sales representative</option>
                    <option value="MEDICAL">Medical representative</option>
                  </Select>
                </Field>
                <Field label="Phone" error={fieldError(repMutation.error, "phone")}>
                  <Input
                    value={repForm.phone}
                    onChange={(e) => setRepForm({ ...repForm, phone: e.target.value })}
                  />
                </Field>
                <Field label="Branch" error={fieldError(repMutation.error, "branch")}>
                  <Select
                    value={repForm.branch}
                    onChange={(e) => setRepForm({ ...repForm, branch: e.target.value })}
                  >
                    <option value="">—</option>
                    {branchesQuery.data?.results.map((branch) => (
                      <option key={branch.id} value={branch.id}>
                        {branch.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="col-span-2 lg:col-span-4">
                  <Button type="submit" disabled={repMutation.isPending}>
                    {repMutation.isPending ? "Saving…" : "Create representative"}
                  </Button>
                </div>
              </form>
            </Card>
          ) : null}
          <Card>
            <CardHeader
              title="Representatives"
              subtitle={repsQuery.data ? `${repsQuery.data.count} rep(s)` : undefined}
            />
            <ErrorBanner error={repsQuery.error} />
            {repsQuery.isLoading ? (
              <Spinner />
            ) : !repsQuery.data || repsQuery.data.results.length === 0 ? (
              <EmptyState message="No representatives yet." />
            ) : (
              <ul className="divide-y divide-slate-100">
                {repsQuery.data.results.map((rep) => (
                  <li
                    key={rep.id}
                    className="flex flex-wrap items-center justify-between gap-2 p-4"
                  >
                    <div>
                      <p className="font-medium">
                        {rep.name}{" "}
                        <span className="font-mono text-xs text-slate-500">{rep.code}</span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {rep.rep_type} · {rep.phone || "no phone"}
                        {rep.branch_name ? ` · ${rep.branch_name}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {rep.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                      <Button size="sm" variant="secondary" onClick={() => setSelected(rep)}>
                        Assignments
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {repsQuery.data && repsQuery.data.count > 0 ? (
              <Pagination
                page={page}
                hasPrevious={Boolean(repsQuery.data.previous)}
                hasNext={Boolean(repsQuery.data.next)}
                onChange={setPage}
              />
            ) : null}
          </Card>
        </>
      ) : (
        <>
          {showTerritoryForm ? (
            <Card>
              <CardHeader title="New territory" subtitle="Region → area → territory hierarchy." />
              <form
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  territoryMutation.mutate(territoryForm);
                }}
                className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4"
              >
                <div className="col-span-2 lg:col-span-4">
                  <ErrorBanner error={territoryMutation.error} />
                </div>
                <Field label="Name" error={fieldError(territoryMutation.error, "name")}>
                  <Input
                    value={territoryForm.name}
                    onChange={(e) => setTerritoryForm({ ...territoryForm, name: e.target.value })}
                    required
                  />
                </Field>
                <Field label="Type" error={fieldError(territoryMutation.error, "territory_type")}>
                  <Select
                    value={territoryForm.territory_type}
                    onChange={(e) =>
                      setTerritoryForm({ ...territoryForm, territory_type: e.target.value })
                    }
                  >
                    <option value="REGION">Region</option>
                    <option value="AREA">Area</option>
                    <option value="TERRITORY">Territory</option>
                  </Select>
                </Field>
                <Field label="Parent" error={fieldError(territoryMutation.error, "parent")}>
                  <Select
                    value={territoryForm.parent}
                    onChange={(e) => setTerritoryForm({ ...territoryForm, parent: e.target.value })}
                  >
                    <option value="">—</option>
                    {territoriesQuery.data?.results.map((territory) => (
                      <option key={territory.id} value={territory.id}>
                        {territory.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="col-span-2 lg:col-span-4">
                  <Button type="submit" disabled={territoryMutation.isPending}>
                    {territoryMutation.isPending ? "Saving…" : "Create territory"}
                  </Button>
                </div>
              </form>
            </Card>
          ) : null}
          <Card>
            <CardHeader
              title="Territories"
              subtitle={
                territoriesQuery.data ? `${territoriesQuery.data.count} territory(ies)` : undefined
              }
            />
            <ErrorBanner error={territoriesQuery.error} />
            {territoriesQuery.isLoading ? (
              <Spinner />
            ) : !territoriesQuery.data || territoriesQuery.data.results.length === 0 ? (
              <EmptyState message="No territories yet." />
            ) : (
              <ul className="divide-y divide-slate-100">
                {territoriesQuery.data.results.map((territory) => (
                  <li key={territory.id} className="flex items-center justify-between p-4 text-sm">
                    <div>
                      <p className="font-medium">{territory.name}</p>
                      <p className="text-xs text-slate-500">
                        {territory.territory_type}
                        {territory.parent_name ? ` · parent: ${territory.parent_name}` : ""}
                      </p>
                    </div>
                    {territory.is_active ? (
                      <Badge tone="green">Active</Badge>
                    ) : (
                      <Badge>Inactive</Badge>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
