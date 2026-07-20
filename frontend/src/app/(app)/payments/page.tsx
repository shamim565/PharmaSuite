"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { CustomerPayment, DailyCollectionReport, Paginated } from "@/lib/types";

export default function PaymentsPage() {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [method, setMethod] = useState("");
  const [reverseFor, setReverseFor] = useState<CustomerPayment | null>(null);
  const [reverseReason, setReverseReason] = useState("");

  const params = new URLSearchParams({ page_size: "50" });
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (method) params.set("method", method);

  const paymentsQuery = useQuery({
    queryKey: ["payments", search, status, method],
    queryFn: () => api.get<Paginated<CustomerPayment>>(`/payments/?${params.toString()}`),
  });
  const dailyQuery = useQuery({
    queryKey: ["daily-collection"],
    queryFn: () => api.get<DailyCollectionReport>("/payments/reports/daily-collection/"),
  });

  const reverseMutation = useMutation({
    mutationFn: () => api.post(`/payments/${reverseFor?.id}/reverse/`, { reason: reverseReason }),
    onSuccess: () => {
      setReverseFor(null);
      setReverseReason("");
      queryClient.invalidateQueries({ queryKey: ["payments"] });
      queryClient.invalidateQueries({ queryKey: ["daily-collection"] });
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      queryClient.invalidateQueries({ queryKey: ["dues"] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Payments & receipts</h1>
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="Search receipt, customer…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-48"
          />
          <Select value={method} onChange={(e) => setMethod(e.target.value)} className="w-32">
            <option value="">All methods</option>
            <option value="CASH">Cash</option>
            <option value="BANK">Bank</option>
            <option value="MFS">MFS</option>
            <option value="CHEQUE">Cheque</option>
          </Select>
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-32">
            <option value="">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="REVERSED">Reversed</option>
          </Select>
        </div>
      </div>

      {dailyQuery.data ? (
        <Card className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase text-slate-500">Collected today ({dailyQuery.data.date})</p>
              <p className="text-2xl font-bold text-emerald-700">{dailyQuery.data.total}</p>
              <p className="text-xs text-slate-500">{dailyQuery.data.payment_count} receipt(s)</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {dailyQuery.data.by_method.map((row) => (
                <span key={row.method} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                  {row.method}: <strong>{row.total}</strong> ({row.count})
                </span>
              ))}
            </div>
            <div className="text-xs text-slate-500">
              {dailyQuery.data.by_collector.map((row) => (
                <p key={`${row.collector}-${row.collector_name}`}>
                  {row.collector_name}: {row.total} ({row.count})
                </p>
              ))}
            </div>
          </div>
        </Card>
      ) : null}

      {reverseFor ? (
        <Card>
          <CardHeader
            title={`Reverse receipt ${reverseFor.number}`}
            subtitle={`${reverseFor.customer_name} · ${reverseFor.amount}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setReverseFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={reverseMutation.error} />
            <Field label="Reason">
              <Input value={reverseReason} onChange={(e) => setReverseReason(e.target.value)} />
            </Field>
            <Button
              variant="danger"
              onClick={() => reverseMutation.mutate()}
              disabled={reverseMutation.isPending || !reverseReason}
            >
              {reverseMutation.isPending ? "Reversing…" : "Reverse receipt"}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Receipts" subtitle={paymentsQuery.data ? `${paymentsQuery.data.count} receipt(s)` : undefined} />
        <ErrorBanner error={paymentsQuery.error} />
        {paymentsQuery.isLoading ? (
          <Spinner />
        ) : !paymentsQuery.data || paymentsQuery.data.results.length === 0 ? (
          <EmptyState message="No receipts found." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {paymentsQuery.data.results.map((payment) => (
              <li key={payment.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    <Link href={`/payments/${payment.id}`} className="text-emerald-700 hover:underline">
                      {payment.number}
                    </Link>{" "}
                    <span className="text-xs text-slate-400">{payment.customer_name}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {payment.business_date} · {payment.method} · {payment.account_name}
                    {payment.collector_name ? ` · by ${payment.collector_name}` : ""} ·{" "}
                    {payment.allocations.length} allocation(s)
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-mono font-semibold">{payment.amount}</span>
                  {payment.status === "ACTIVE" ? <Badge tone="green">Active</Badge> : <Badge tone="rose">Reversed</Badge>}
                  <Link href={`/payments/${payment.id}`}>
                    <Button size="sm" variant="secondary">
                      Receipt
                    </Button>
                  </Link>
                  {payment.status === "ACTIVE" && hasPerm("PAYMENT_REVERSE") ? (
                    <Button size="sm" variant="ghost" onClick={() => setReverseFor(payment)}>
                      Reverse
                    </Button>
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
