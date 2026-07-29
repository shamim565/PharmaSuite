"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Spinner } from "@/components/ui";
import { api, apiDownload } from "@/lib/api";
import type { AuditLogEntry, Paginated } from "@/lib/types";

export default function AuditPage() {
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const params = new URLSearchParams({ page_size: "25", page: String(page) });
  if (entityType) params.set("entity_type", entityType);
  if (action) params.set("action", action);
  if (search) params.set("search", search);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);

  const { data, isLoading, error } = useQuery({
    queryKey: ["audit-logs", entityType, action, search, dateFrom, dateTo, page],
    queryFn: () => api.get<Paginated<AuditLogEntry>>(`/audit-logs/?${params.toString()}`),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Audit log</h1>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => apiDownload(`/audit-logs/export/?${params.toString()}`, "audit-log.csv")}
        >
          Export CSV
        </Button>
      </div>

      <Card className="p-4">
        <div className="grid grid-cols-2 items-end gap-3 lg:grid-cols-5">
          <Field label="Entity type">
            <Input
              value={entityType}
              onChange={(e) => {
                setEntityType(e.target.value);
                setPage(1);
              }}
              placeholder="Sale, Purchase, User…"
            />
          </Field>
          <Field label="Action">
            <Input
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
              placeholder="confirm, cancel, login…"
            />
          </Field>
          <Field label="Request id / search">
            <Input value={search} onChange={(e) => setSearch(e.target.value)} />
          </Field>
          <Field label="From">
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Events"
          subtitle={data ? `${data.count} event(s) · immutable, 7-year retention` : undefined}
        />
        <ErrorBanner error={error} />
        {isLoading ? (
          <Spinner />
        ) : !data || data.results.length === 0 ? (
          <EmptyState message="No audit events match." />
        ) : (
          <>
            <ul className="divide-y divide-slate-100">
              {data.results.map((entry) => (
                <li key={entry.id} className="space-y-1 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-sm">
                        <Badge tone={entry.actor_type === "SYSTEM" ? "blue" : "slate"}>{entry.action}</Badge>{" "}
                        <span className="font-medium">{entry.entity_type}</span>{" "}
                        <span className="font-mono text-xs text-slate-400">
                          {entry.entity_id ? entry.entity_id.slice(0, 8) : ""}
                        </span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {new Date(entry.created_at).toLocaleString()} · {entry.actor_name || "system"}
                        {entry.branch_name ? ` · ${entry.branch_name}` : ""}
                        {entry.ip ? ` · ${entry.ip}` : ""}
                      </p>
                    </div>
                    <span className="font-mono text-[10px] text-slate-400">req {entry.request_id || "—"}</span>
                  </div>
                  {entry.before || entry.after ? (
                    <details className="text-xs">
                      <summary className="cursor-pointer text-emerald-700">Show changes</summary>
                      <div className="mt-1 grid gap-2 lg:grid-cols-2">
                        <pre className="max-h-48 overflow-auto rounded-lg bg-rose-50 p-2 text-rose-900">
                          {entry.before ? JSON.stringify(entry.before, null, 2) : "—"}
                        </pre>
                        <pre className="max-h-48 overflow-auto rounded-lg bg-emerald-50 p-2 text-emerald-900">
                          {entry.after ? JSON.stringify(entry.after, null, 2) : "—"}
                        </pre>
                      </div>
                    </details>
                  ) : null}
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm">
              <button
                className="rounded px-2 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
                disabled={!data.previous}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                ← Previous
              </button>
              <span className="text-xs text-slate-400">Page {page}</span>
              <button
                className="rounded px-2 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
                disabled={!data.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
