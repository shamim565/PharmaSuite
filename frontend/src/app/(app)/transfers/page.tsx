"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import { Badge, Button, Card, CardHeader, ConfirmButton, EmptyState, ErrorBanner, Field, Input, Pagination, Select, Spinner } from "@/components/ui";
import { MedicineCombobox } from "@/components/medicine-combobox";
import { ApiError, api, newIdempotencyKey } from "@/lib/api";
import { formatDate, formatMoney, formatQty } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type { Branch, MedicineBatch, Paginated, StockTransfer } from "@/lib/types";

type DraftRow = { key: number; medicine: string; batch: string; qty: string; pool: string };

const newRow = (key: number): DraftRow => ({
  key,
  medicine: "",
  batch: "",
  qty: "",
  pool: "SALEABLE",
});

function TransferRow({
  row,
  index,
  fromBranch,
  removable,
  onChange,
  onRemove,
}: {
  row: DraftRow;
  index: number;
  fromBranch: string;
  removable: boolean;
  onChange: (patch: Partial<DraftRow>) => void;
  onRemove: () => void;
}) {
  const batchesQuery = useQuery({
    queryKey: ["batches", "transfer", fromBranch, row.medicine],
    queryFn: () =>
      api.get<Paginated<MedicineBatch>>(
        `/batches/?page_size=100&branch=${fromBranch}&medicine=${row.medicine}`,
      ),
    enabled: Boolean(fromBranch && row.medicine),
  });

  return (
    <div className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 p-3 lg:grid-cols-5">
      <div className="col-span-2">
        <Field label={`Medicine ${index + 1}`}>
          <MedicineCombobox
            value={row.medicine}
            onChange={(id) => onChange({ medicine: id, batch: "" })}
          />
        </Field>
      </div>
      <Field label="Source batch">
        <Select
          value={row.batch}
          onChange={(event) => onChange({ batch: event.target.value })}
          disabled={!row.medicine || !fromBranch}
          required
        >
          <option value="">Select…</option>
          {batchesQuery.data?.results.map((batch) => (
            <option key={batch.id} value={batch.id}>
              {batch.batch_number} · qty {formatQty(batch.qty_on_hand)} · exp {batch.expiry_date ? formatDate(batch.expiry_date) : "—"}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Qty">
        <Input
          type="number"
          step="0.001"
          min="0.001"
          value={row.qty}
          onChange={(event) => onChange({ qty: event.target.value })}
          required
        />
      </Field>
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Field label="Pool">
            <Select value={row.pool} onChange={(event) => onChange({ pool: event.target.value })}>
              <option value="SALEABLE">Saleable</option>
              <option value="PROMO">Promotional</option>
              <option value="QUARANTINE">Quarantine</option>
            </Select>
          </Field>
        </div>
        {removable ? (
          <Button type="button" size="sm" variant="ghost" onClick={onRemove}>
            Remove
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export default function TransfersPage() {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const canTransfer = hasPerm("STOCK_TRANSFER");
  const canView = canTransfer || hasPerm("STOCK_VIEW");

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [fromBranch, setFromBranch] = useState("");
  const [toBranch, setToBranch] = useState("");
  const [notes, setNotes] = useState("");
  const [rows, setRows] = useState<DraftRow[]>([newRow(1)]);
  const [rowSeq, setRowSeq] = useState(2);
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey());
  const debouncedSearch = useDebouncedValue(search);

  const transferParams = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) transferParams.set("search", debouncedSearch);

  const transfersQuery = useQuery({
    queryKey: ["transfers", debouncedSearch, page],
    queryFn: () =>
      api.get<Paginated<StockTransfer>>(`/inventory/transfers/?${transferParams.toString()}`),
    enabled: canView,
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "select"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=100&status=ACTIVE"),
    enabled: canView,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["transfers"] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["batches"] });
    queryClient.invalidateQueries({ queryKey: ["stock-summary"] });
  };

  const createMutation = useMutation({
    meta: { successMessage: "Transfer saved as draft" },
    mutationFn: () =>
      api.postWithKey<StockTransfer>(
        "/inventory/transfers/",
        {
          from_branch: fromBranch,
          to_branch: toBranch,
          notes,
          items: rows.map((row) => ({
            medicine: row.medicine,
            batch: row.batch,
            qty: row.qty,
            pool: row.pool,
          })),
        },
        idempotencyKey,
      ),
    onSuccess: () => {
      setFromBranch("");
      setToBranch("");
      setNotes("");
      setRows([newRow(1)]);
      setRowSeq(2);
      setIdempotencyKey(newIdempotencyKey());
      setShowForm(false);
      invalidate();
    },
  });

  const confirmMutation = useMutation({
    meta: { successMessage: "Transfer confirmed" },
    mutationFn: (transfer: StockTransfer) =>
      api.post(`/inventory/transfers/${transfer.id}/confirm/`, {}),
    onSuccess: () => invalidate(),
  });

  const updateRow = (key: number, patch: Partial<DraftRow>) => {
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate();
  };

  if (!canView) {
    return (
      <Card>
        <EmptyState message="You need STOCK_VIEW or STOCK_TRANSFER to view transfers." />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Stock transfers</h1>
        {canTransfer ? (
          <Button size="sm" onClick={() => setShowForm((value) => !value)}>
            {showForm ? "Close" : "New transfer"}
          </Button>
        ) : null}
      </div>

      {showForm && canTransfer ? (
        <Card>
          <CardHeader
            title="New transfer"
            subtitle="Stock moves only when the transfer is confirmed; the destination branch batch is created automatically."
          />
          <form onSubmit={onSubmit} className="space-y-3 p-4">
            <ErrorBanner error={createMutation.error} />
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Field label="From branch" error={fieldError("from_branch")}>
                <Select
                  value={fromBranch}
                  onChange={(event) => {
                    setFromBranch(event.target.value);
                    setRows([newRow(1)]);
                    setRowSeq(2);
                  }}
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
              <Field label="To branch" error={fieldError("to_branch")}>
                <Select value={toBranch} onChange={(event) => setToBranch(event.target.value)} required>
                  <option value="">Select…</option>
                  {branchesQuery.data?.results
                    .filter((branch) => branch.id !== fromBranch)
                    .map((branch) => (
                      <option key={branch.id} value={branch.id}>
                        {branch.name}
                      </option>
                    ))}
                </Select>
              </Field>
              <div className="col-span-2">
                <Field label="Notes">
                  <Input value={notes} onChange={(event) => setNotes(event.target.value)} />
                </Field>
              </div>
            </div>

            <div className="space-y-2">
              {!fromBranch ? (
                <p className="text-xs text-slate-500">Select a source branch to pick batches.</p>
              ) : null}
              {rows.map((row, index) => (
                <TransferRow
                  key={row.key}
                  row={row}
                  index={index}
                  fromBranch={fromBranch}
                  removable={rows.length > 1}
                  onChange={(patch) => updateRow(row.key, patch)}
                  onRemove={() => setRows((prev) => prev.filter((item) => item.key !== row.key))}
                />
              ))}
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => {
                  setRows((prev) => [...prev, newRow(rowSeq)]);
                  setRowSeq((value) => value + 1);
                }}
              >
                Add line
              </Button>
            </div>

            <Button
              type="submit"
              disabled={
                createMutation.isPending ||
                !fromBranch ||
                !toBranch ||
                rows.some((row) => !row.medicine || !row.batch || !row.qty)
              }
            >
              {createMutation.isPending ? "Saving…" : "Save draft"}
            </Button>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Transfer register"
          subtitle={transfersQuery.data ? `${transfersQuery.data.count} transfer(s)` : undefined}
          action={
            <Input
              placeholder="Search number, medicine…"
              aria-label="Search transfers"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              className="w-52"
            />
          }
        />
        <ErrorBanner error={transfersQuery.error} />
        <ErrorBanner error={confirmMutation.error} />
        {transfersQuery.isLoading ? (
          <Spinner />
        ) : !transfersQuery.data || transfersQuery.data.results.length === 0 ? (
          <EmptyState message="No transfers yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {transfersQuery.data.results.map((transfer) => (
              <li key={transfer.id} className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium">
                      {transfer.number ?? "Draft"}{" "}
                      <span className="text-xs text-slate-500">
                        {transfer.from_branch_name} → {transfer.to_branch_name}
                      </span>
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatDate(transfer.business_date)} · {transfer.items.length} line(s) · requested by{" "}
                      {transfer.requested_by_name || "—"}
                      {transfer.confirmed_by_name ? ` · confirmed by ${transfer.confirmed_by_name}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={transfer.status === "CONFIRMED" ? "green" : "amber"}>
                      {transfer.status}
                    </Badge>
                    {transfer.status === "DRAFT" && canTransfer ? (
                      <ConfirmButton
                        size="sm"
                        confirmLabel="Confirm transfer?"
                        onConfirm={() => confirmMutation.mutate(transfer)}
                        disabled={confirmMutation.isPending}
                      >
                        Confirm
                      </ConfirmButton>
                    ) : null}
                  </div>
                </div>
                <ul className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                  {transfer.items.map((item) => (
                    <li key={item.id}>
                      {item.medicine_name} ({item.medicine_code}) · batch {item.batch_number} · qty{" "}
                      {formatQty(item.qty)} · {item.pool} @ {formatMoney(item.unit_cost)}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
        {transfersQuery.data && transfersQuery.data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(transfersQuery.data.previous)}
            hasNext={Boolean(transfersQuery.data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
