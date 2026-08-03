"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { Cheque, Paginated } from "@/lib/types";

const STATUS_TONE: Record<string, "green" | "amber" | "rose" | "slate" | "blue"> = {
  CLEARED: "green",
  PAID: "green",
  PENDING_DEPOSIT: "blue",
  PENDING: "blue",
  DEPOSITED: "amber",
  BOUNCED: "rose",
  STOPPED: "rose",
};

const STATUS_LABEL: Record<string, string> = {
  PENDING_DEPOSIT: "Pending deposit",
  DEPOSITED: "Deposited",
  CLEARED: "Cleared",
  BOUNCED: "Bounced",
  PENDING: "Pending",
  PAID: "Paid",
  STOPPED: "Stopped",
};

export default function ChequesPage() {
  const { hasPerm } = useAuth();
  const queryClient = useQueryClient();
  const [direction, setDirection] = useState<"RECEIVED" | "ISSUED">("RECEIVED");
  const [form, setForm] = useState({
    number: "",
    bank_name: "",
    bank_branch: "",
    amount: "",
    date_issued: "",
    customer: "",
    supplier: "",
    notes: "",
  });
  const [actionFor, setActionFor] = useState<{ cheque: Cheque; action: string } | null>(null);
  const [actionNotes, setActionNotes] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const params = new URLSearchParams({ page_size: "100" });
  if (filterStatus) params.set("status", filterStatus);

  const chequesQuery = useQuery({
    queryKey: ["cheques", filterStatus],
    queryFn: () => api.get<Paginated<Cheque>>(`/cheques/?${params.toString()}`),
  });
  const customersQuery = useQuery({
    queryKey: ["customers", "cheque"],
    queryFn: () => api.get<Paginated<{ id: string; name: string }>>("/customers/?page_size=200"),
  });
  const suppliersQuery = useQuery({
    queryKey: ["suppliers", "cheque"],
    queryFn: () => api.get<Paginated<{ id: string; name: string }>>("/suppliers/?page_size=200"),
  });

  const createMutation = useMutation({
    mutationFn: () => api.post("/cheques/", { direction, ...form }),
    onSuccess: () => {
      setForm({ number: "", bank_name: "", bank_branch: "", amount: "", date_issued: "", customer: "", supplier: "", notes: "" });
      queryClient.invalidateQueries({ queryKey: ["cheques"] });
    },
  });
  const actionMutation = useMutation({
    mutationFn: () => api.post(`/cheques/${actionFor?.cheque.id}/${actionFor?.action}/`, { notes: actionNotes }),
    onSuccess: () => {
      setActionFor(null);
      setActionNotes("");
      queryClient.invalidateQueries({ queryKey: ["cheques"] });
    },
  });

  const actionsFor = (cheque: Cheque): Array<{ action: string; label: string }> => {
    if (cheque.direction === "RECEIVED") {
      if (cheque.status === "PENDING_DEPOSIT") return [{ action: "deposit", label: "Deposit" }, { action: "bounce", label: "Bounce" }, { action: "stop", label: "Stop" }];
      if (cheque.status === "DEPOSITED") return [{ action: "clear", label: "Clear" }, { action: "bounce", label: "Bounce" }, { action: "stop", label: "Stop" }];
      return [];
    }
    if (cheque.status === "PENDING") return [{ action: "mark-paid", label: "Mark paid" }, { action: "stop", label: "Stop" }];
    return [];
  };

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-800">Cheques</h1>

      {hasPerm("CHEQUE_MANAGE") ? (
        <Card>
          <CardHeader title={direction === "RECEIVED" ? "Register received cheque" : "Register issued cheque"} />
          <div className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <ErrorBanner error={createMutation.error} />
            <div className="col-span-2 flex gap-2 lg:col-span-4">
              <button
                onClick={() => setDirection("RECEIVED")}
                className={`rounded-full px-3 py-1.5 text-sm font-medium ${direction === "RECEIVED" ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-600"}`}
              >
                Received from customer
              </button>
              <button
                onClick={() => setDirection("ISSUED")}
                className={`rounded-full px-3 py-1.5 text-sm font-medium ${direction === "ISSUED" ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-600"}`}
              >
                Issued to supplier
              </button>
            </div>
            <Field label="Cheque number">
              <Input value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} />
            </Field>
            <Field label="Bank">
              <Input value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} />
            </Field>
            <Field label="Bank branch">
              <Input value={form.bank_branch} onChange={(e) => setForm({ ...form, bank_branch: e.target.value })} />
            </Field>
            <Field label="Amount (BDT)">
              <Input value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            </Field>
            <Field label="Date issued">
              <Input type="date" value={form.date_issued} onChange={(e) => setForm({ ...form, date_issued: e.target.value })} />
            </Field>
            {direction === "RECEIVED" ? (
              <Field label="Customer">
                <Select value={form.customer} onChange={(e) => setForm({ ...form, customer: e.target.value })}>
                  <option value="">Select customer</option>
                  {customersQuery.data?.results.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </Select>
              </Field>
            ) : (
              <Field label="Supplier">
                <Select value={form.supplier} onChange={(e) => setForm({ ...form, supplier: e.target.value })}>
                  <option value="">Select supplier</option>
                  {suppliersQuery.data?.results.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </Select>
              </Field>
            )}
            <div className="col-span-2 lg:col-span-4">
              <Button
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending || !form.number || !form.bank_name || !form.amount || !form.date_issued || (direction === "RECEIVED" ? !form.customer : !form.supplier)}
              >
                {createMutation.isPending ? "Saving…" : "Register cheque"}
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {actionFor ? (
        <Card>
          <CardHeader
            title={`${actionFor.action.replace("-", " ")} — ${actionFor.cheque.number}`}
            action={
              <Button size="sm" variant="secondary" onClick={() => setActionFor(null)}>
                Cancel
              </Button>
            }
          />
          <div className="space-y-3 p-4">
            <ErrorBanner error={actionMutation.error} />
            <Field label="Notes (optional)">
              <Input value={actionNotes} onChange={(e) => setActionNotes(e.target.value)} />
            </Field>
            <Button
              onClick={() => actionMutation.mutate()}
              disabled={actionMutation.isPending}
              variant={actionFor.action === "bounce" || actionFor.action === "stop" ? "danger" : "secondary"}
            >
              {actionMutation.isPending ? "Saving…" : `Confirm ${actionFor.action.replace("-", " ")}`}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Cheque register"
          subtitle={chequesQuery.data ? `${chequesQuery.data.count} cheque(s)` : undefined}
          action={
            <Select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
              <option value="">All statuses</option>
              {Object.entries(STATUS_LABEL).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </Select>
          }
        />
        <ErrorBanner error={chequesQuery.error} />
        {chequesQuery.isLoading ? (
          <Spinner />
        ) : !chequesQuery.data || chequesQuery.data.results.length === 0 ? (
          <EmptyState message="No cheques yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {chequesQuery.data.results.map((cheque) => (
              <li key={cheque.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    {cheque.direction === "RECEIVED" ? cheque.customer_name || "customer" : cheque.supplier_name || "supplier"} · {cheque.number}
                  </p>
                  <p className="text-xs text-slate-500">
                    {cheque.bank_name}{cheque.bank_branch ? `, ${cheque.bank_branch}` : ""} · issued {cheque.date_issued} · {Number(cheque.amount).toFixed(2)}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={STATUS_TONE[cheque.status] ?? "slate"}>{STATUS_LABEL[cheque.status]}</Badge>
                  {hasPerm("CHEQUE_MANAGE")
                    ? actionsFor(cheque).map((item) => (
                        <Button
                          key={item.action}
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setActionFor({ cheque, action: item.action });
                            setActionNotes("");
                          }}
                        >
                          {item.label}
                        </Button>
                      ))
                    : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}