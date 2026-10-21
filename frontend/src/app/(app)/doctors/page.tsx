"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { useAuth } from "@/app/providers";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmButton,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Pagination,
  Select,
  Spinner,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useDebouncedValue } from "@/lib/hooks";
import type {
  DoctorChamber,
  Branch,
  Doctor,
  DoctorMedicine,
  DoctorVisit,
  Medicine,
  MedicineBatch,
  Paginated,
  Representative,
  Territory,
} from "@/lib/types";

const emptyForm = {
  code: "",
  name: "",
  specialty: "",
  category: "B",
  doctor_type: "CONSULTANT",
  phone: "",
  registration_no: "",
  territory: "",
};

const VISIT_STATUS_LABEL: Record<string, string> = {
  PLANNED: "Planned",
  COMPLETED: "Completed",
  MISSED: "Missed",
  CANCELLED: "Cancelled",
};

function DoctorPanel({ doctor, onClose }: { doctor: Doctor; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { user, hasPerm } = useAuth();
  const canManageDoctors = hasPerm("DOCTOR_MANAGE");
  const canManageVisits = hasPerm("VISIT_MANAGE");
  const [mappingMedicine, setMappingMedicine] = useState("");
  const [mappingPriority, setMappingPriority] = useState("HIGH");
  const [visitRep, setVisitRep] = useState("");
  const [visitPurpose, setVisitPurpose] = useState("");
  const [visitOutcome, setVisitOutcome] = useState("INTERESTED");
  const [visitNotes, setVisitNotes] = useState("");
  const [visitNext, setVisitNext] = useState("");
  const [planDate, setPlanDate] = useState("");
  const [logTarget, setLogTarget] = useState("");
  const [visitActionFor, setVisitActionFor] = useState<{
    visit: DoctorVisit;
    kind: "miss" | "cancel" | "reverse";
  } | null>(null);
  const [visitReason, setVisitReason] = useState("");
  const [sampleMedicine, setSampleMedicine] = useState("");
  const [sampleBatch, setSampleBatch] = useState("");
  const [sampleQty, setSampleQty] = useState("");

  const mappingsQuery = useQuery({
    queryKey: ["doctor-mappings", doctor.id],
    queryFn: () => api.get<DoctorMedicine[]>(`/doctors/${doctor.id}/medicines/`),
  });
  const visitsQuery = useQuery({
    queryKey: ["doctor-visits", doctor.id],
    queryFn: () =>
      api.get<Paginated<DoctorVisit>>(`/doctor-visits/?doctor=${doctor.id}&page_size=20`),
  });
  const medicinesQuery = useQuery({
    queryKey: ["medicines", "select"],
    queryFn: () => api.get<Paginated<Medicine>>("/medicines/?page_size=200&is_active=true"),
  });
  const repsQuery = useQuery({
    queryKey: ["reps", "medical"],
    queryFn: () =>
      api.get<Paginated<Representative>>(
        "/representatives/?page_size=100&is_active=true&rep_type=MEDICAL",
      ),
  });
  const branchesQuery = useQuery({
    queryKey: ["branches", "visit-fallback"],
    queryFn: () => api.get<Paginated<Branch>>("/branches/?page_size=1&status=ACTIVE"),
    enabled: !user?.default_branch_id,
  });
  const visitBranchId = user?.default_branch_id ?? branchesQuery.data?.results[0]?.id ?? "";
  const batchesQuery = useQuery({
    queryKey: ["batches", "sample", sampleMedicine, visitBranchId],
    queryFn: () =>
      api.get<Paginated<MedicineBatch>>(
        `/batches/?page_size=100&medicine=${sampleMedicine}&branch=${visitBranchId}`,
      ),
    enabled: Boolean(sampleMedicine && visitBranchId),
  });

  const [chamberForm, setChamberForm] = useState({ name: "", address: "", visiting_hours: "" });

  const chambersQuery = useQuery({
    queryKey: ["doctor-chambers", doctor.id],
    queryFn: () =>
      api.get<{ count: number; results: DoctorChamber[] }>(`/doctors/${doctor.id}/chambers/`),
  });

  const chamberMutation = useMutation({
    meta: { successMessage: "Chamber added" },
    mutationFn: () => api.post(`/doctors/${doctor.id}/chambers/`, chamberForm),
    onSuccess: () => {
      setChamberForm({ name: "", address: "", visiting_hours: "" });
      queryClient.invalidateQueries({ queryKey: ["doctor-chambers", doctor.id] });
    },
  });

  const deleteChamberMutation = useMutation({
    meta: { successMessage: "Chamber removed" },
    mutationFn: (chamber: DoctorChamber) =>
      api.delete(`/doctors/${doctor.id}/chambers/${chamber.id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["doctor-chambers", doctor.id] }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["doctor-mappings", doctor.id] });
    queryClient.invalidateQueries({ queryKey: ["doctor-visits", doctor.id] });
    queryClient.invalidateQueries({ queryKey: ["doctors"] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["batches"] });
  };

  const mappingMutation = useMutation({
    meta: { successMessage: "Mapping added" },
    mutationFn: () =>
      api.post(`/doctors/${doctor.id}/medicines/`, {
        medicine: mappingMedicine,
        priority: mappingPriority,
      }),
    onSuccess: () => {
      setMappingMedicine("");
      invalidate();
    },
  });
  const endMappingMutation = useMutation({
    meta: { successMessage: "Mapping ended" },
    mutationFn: (mapping: DoctorMedicine) => api.post(`/doctor-medicines/${mapping.id}/end/`),
    onSuccess: () => invalidate(),
  });

  const resetLogForm = () => {
    setLogTarget("");
    setVisitPurpose("");
    setVisitNotes("");
    setVisitNext("");
    setSampleMedicine("");
    setSampleBatch("");
    setSampleQty("");
  };

  const planMutation = useMutation({
    meta: { successMessage: "Visit planned" },
    mutationFn: () =>
      api.post<DoctorVisit>("/doctor-visits/", {
        doctor: doctor.id,
        representative: visitRep,
        branch: visitBranchId,
        planned_date: planDate,
        purpose: visitPurpose,
      }),
    onSuccess: () => {
      setVisitRep("");
      setVisitPurpose("");
      setPlanDate("");
      invalidate();
    },
  });

  const logMutation = useMutation({
    meta: { successMessage: "Visit completed" },
    mutationFn: async () => {
      let visitId = logTarget;
      if (!visitId) {
        const today = new Date();
        const todayIso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
        const created = await api.post<DoctorVisit>("/doctor-visits/", {
          doctor: doctor.id,
          representative: visitRep,
          branch: visitBranchId,
          planned_date: todayIso,
          purpose: visitPurpose,
        });
        visitId = created.id;
      }
      const payload: Record<string, unknown> = {
        outcome: visitOutcome,
        products_discussed: mappingsQuery.data?.map((mapping) => mapping.medicine) ?? [],
        notes: visitNotes,
        next_visit_date: visitNext || null,
      };
      if (sampleMedicine && sampleBatch && sampleQty) {
        payload.samples = [{ medicine: sampleMedicine, batch: sampleBatch, qty: sampleQty }];
      }
      return api.post(`/doctor-visits/${visitId}/complete/`, payload);
    },
    onSuccess: () => {
      resetLogForm();
      invalidate();
    },
  });

  const missMutation = useMutation({
    meta: { successMessage: "Visit marked missed" },
    mutationFn: () =>
      api.post(`/doctor-visits/${visitActionFor?.visit.id}/miss/`, { reason: visitReason }),
    onSuccess: () => {
      setVisitActionFor(null);
      setVisitReason("");
      invalidate();
    },
  });

  const cancelMutation = useMutation({
    meta: { successMessage: "Visit cancelled" },
    mutationFn: () =>
      api.post(`/doctor-visits/${visitActionFor?.visit.id}/cancel/`, { reason: visitReason }),
    onSuccess: () => {
      setVisitActionFor(null);
      setVisitReason("");
      invalidate();
    },
  });

  const reverseSamplesMutation = useMutation({
    meta: { successMessage: "Samples reversed" },
    mutationFn: () =>
      api.post(`/doctor-visits/${visitActionFor?.visit.id}/reverse-samples/`, {
        reason: visitReason,
      }),
    onSuccess: () => {
      setVisitActionFor(null);
      setVisitReason("");
      invalidate();
    },
  });

  return (
    <Card>
      <CardHeader
        title={`${doctor.name} (${doctor.code})`}
        subtitle={`${doctor.specialty || "—"} · category ${doctor.category} · ${doctor.territory_name || "no territory"}`}
        action={
          <Button size="sm" variant="secondary" onClick={onClose}>
            Close
          </Button>
        }
      />
      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Promoted medicines</p>
          <ErrorBanner error={mappingMutation.error} />
          {mappingsQuery.isLoading ? (
            <Spinner />
          ) : !mappingsQuery.data || mappingsQuery.data.length === 0 ? (
            <EmptyState message="No mappings yet." />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {mappingsQuery.data.map((mapping) => (
                <li
                  key={mapping.id}
                  className="flex items-center justify-between px-3 py-2 text-sm"
                >
                  <div>
                    <p className="font-medium">{mapping.medicine_name}</p>
                    <p className="text-xs text-slate-500">
                      {mapping.medicine_code} · {mapping.priority || "—"} · since{" "}
                      {formatDate(mapping.effective_from)}
                    </p>
                  </div>
                  {canManageDoctors ? (
                    <ConfirmButton
                      size="sm"
                      variant="ghost"
                      confirmLabel="End mapping?"
                      onConfirm={() => endMappingMutation.mutate(mapping)}
                    >
                      End
                    </ConfirmButton>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {canManageDoctors ? (
            <div className="flex flex-wrap items-end gap-2">
              <div className="w-48">
                <Field label="Medicine">
                  <Select
                    value={mappingMedicine}
                    onChange={(e) => setMappingMedicine(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {medicinesQuery.data?.results.map((medicine) => (
                      <option key={medicine.id} value={medicine.id}>
                        {medicine.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <div className="w-32">
                <Field label="Priority">
                  <Select
                    value={mappingPriority}
                    onChange={(e) => setMappingPriority(e.target.value)}
                  >
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </Select>
                </Field>
              </div>
              <Button
                size="sm"
                onClick={() => mappingMutation.mutate()}
                disabled={!mappingMedicine || mappingMutation.isPending}
              >
                Add mapping
              </Button>
            </div>
          ) : null}
        </div>

        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Chambers</p>
          <ErrorBanner error={chamberMutation.error} />
          {chambersQuery.isLoading ? (
            <Spinner />
          ) : !chambersQuery.data || chambersQuery.data.results.length === 0 ? (
            <EmptyState message="No chambers yet." />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {chambersQuery.data.results.map((chamber) => (
                <li
                  key={chamber.id}
                  className="flex items-center justify-between px-3 py-2 text-sm"
                >
                  <div>
                    <p className="font-medium">{chamber.name}</p>
                    <p className="text-xs text-slate-500">
                      {chamber.address || "—"}
                      {chamber.visiting_hours ? ` · ${chamber.visiting_hours}` : ""}
                    </p>
                  </div>
                  {canManageDoctors ? (
                    <ConfirmButton
                      size="sm"
                      variant="ghost"
                      confirmLabel="Remove?"
                      onConfirm={() => deleteChamberMutation.mutate(chamber)}
                    >
                      Remove
                    </ConfirmButton>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {canManageDoctors ? (
            <div className="flex flex-wrap items-end gap-2">
              <div className="w-40">
                <Field label="Chamber name">
                  <Input
                    value={chamberForm.name}
                    onChange={(e) => setChamberForm({ ...chamberForm, name: e.target.value })}
                  />
                </Field>
              </div>
              <div className="w-48">
                <Field label="Address">
                  <Input
                    value={chamberForm.address}
                    onChange={(e) => setChamberForm({ ...chamberForm, address: e.target.value })}
                  />
                </Field>
              </div>
              <div className="w-36">
                <Field label="Visiting hours">
                  <Input
                    value={chamberForm.visiting_hours}
                    onChange={(e) =>
                      setChamberForm({ ...chamberForm, visiting_hours: e.target.value })
                    }
                  />
                </Field>
              </div>
              <Button
                size="sm"
                onClick={() => chamberMutation.mutate()}
                disabled={!chamberForm.name || chamberMutation.isPending}
              >
                Add chamber
              </Button>
            </div>
          ) : null}
        </div>

        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Visit history</p>
          <ErrorBanner
            error={missMutation.error ?? cancelMutation.error ?? reverseSamplesMutation.error}
          />
          {visitActionFor ? (
            <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-medium text-amber-800">
                {visitActionFor.kind === "miss"
                  ? "Mark visit missed"
                  : visitActionFor.kind === "cancel"
                    ? "Cancel visit"
                    : "Reverse issued samples"}{" "}
                — {visitActionFor.visit.representative_name} (
                {visitActionFor.visit.planned_date
                  ? formatDate(visitActionFor.visit.planned_date)
                  : "no date"}
                )
              </p>
              <Input
                placeholder="Reason"
                aria-label="Reason"
                value={visitReason}
                onChange={(event) => setVisitReason(event.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="danger"
                  disabled={
                    !visitReason ||
                    missMutation.isPending ||
                    cancelMutation.isPending ||
                    reverseSamplesMutation.isPending
                  }
                  onClick={() => {
                    if (visitActionFor.kind === "miss") missMutation.mutate();
                    else if (visitActionFor.kind === "cancel") cancelMutation.mutate();
                    else reverseSamplesMutation.mutate();
                  }}
                >
                  {visitActionFor.kind === "miss"
                    ? "Mark missed"
                    : visitActionFor.kind === "cancel"
                      ? "Cancel visit"
                      : "Reverse samples"}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setVisitActionFor(null)}>
                  Close
                </Button>
              </div>
            </div>
          ) : null}
          {visitsQuery.isLoading ? (
            <Spinner />
          ) : !visitsQuery.data || visitsQuery.data.results.length === 0 ? (
            <EmptyState message="No visits yet." />
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {visitsQuery.data.results.map((visit) => (
                <li key={visit.id} className="px-3 py-2 text-sm">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{visit.representative_name}</p>
                    <Badge
                      tone={
                        visit.status === "COMPLETED"
                          ? "green"
                          : visit.status === "MISSED"
                            ? "rose"
                            : visit.status === "CANCELLED"
                              ? "slate"
                              : "amber"
                      }
                    >
                      {VISIT_STATUS_LABEL[visit.status] ?? visit.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    {formatDate(visit.visited_at ?? visit.planned_date)} ·{" "}
                    {visit.outcome || visit.missed_reason || visit.cancel_reason || "—"}
                    {visit.next_visit_date ? ` · next ${formatDate(visit.next_visit_date)}` : ""}
                  </p>
                  {visit.samples.length > 0 ? (
                    <p className="text-xs text-primary-700">
                      Samples:{" "}
                      {visit.samples
                        .map(
                          (sample) =>
                            `${sample.medicine_name} ×${sample.qty}${sample.reversed ? " (reversed)" : ""}`,
                        )
                        .join(", ")}
                    </p>
                  ) : null}
                  {canManageVisits &&
                  visit.status === "COMPLETED" &&
                  visit.samples.some((sample) => !sample.reversed) ? (
                    <div className="mt-1 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setVisitActionFor({ visit, kind: "reverse" });
                          setVisitReason("");
                        }}
                      >
                        Reverse samples
                      </Button>
                    </div>
                  ) : null}
                  {canManageVisits && visit.status === "PLANNED" ? (
                    <div className="mt-1 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          setLogTarget(visit.id);
                          setVisitRep(visit.representative);
                        }}
                      >
                        Log visit
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setVisitActionFor({ visit, kind: "miss" });
                          setVisitReason("");
                        }}
                      >
                        Mark missed
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setVisitActionFor({ visit, kind: "cancel" });
                          setVisitReason("");
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        {canManageVisits ? (
          <div className="grid gap-4 lg:col-span-2 lg:grid-cols-2">
            <div className="space-y-3 rounded-lg border border-slate-200 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Plan a visit</p>
              <ErrorBanner error={planMutation.error} />
              <div className="grid grid-cols-2 gap-3">
                <Field label="Representative (MR)">
                  <Select value={visitRep} onChange={(e) => setVisitRep(e.target.value)}>
                    <option value="">Select…</option>
                    {repsQuery.data?.results.map((rep) => (
                      <option key={rep.id} value={rep.id}>
                        {rep.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Planned date">
                  <Input
                    type="date"
                    value={planDate}
                    onChange={(e) => setPlanDate(e.target.value)}
                  />
                </Field>
                <div className="col-span-2">
                  <Field label="Purpose">
                    <Input value={visitPurpose} onChange={(e) => setVisitPurpose(e.target.value)} />
                  </Field>
                </div>
                <div className="col-span-2">
                  <Button
                    onClick={() => planMutation.mutate()}
                    disabled={planMutation.isPending || !visitRep || !planDate || !visitBranchId}
                  >
                    {planMutation.isPending ? "Saving…" : "Plan visit"}
                  </Button>
                </div>
              </div>
            </div>

            <div className="space-y-3 rounded-lg border border-slate-200 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">
                Log a completed visit
              </p>
              <ErrorBanner error={logMutation.error} />
              <div className="grid grid-cols-2 gap-3">
                <Field label="Visit">
                  <Select
                    value={logTarget}
                    onChange={(e) => {
                      setLogTarget(e.target.value);
                      if (!e.target.value) setVisitRep("");
                      else {
                        const target = visitsQuery.data?.results.find(
                          (item) => item.id === e.target.value,
                        );
                        if (target) setVisitRep(target.representative);
                      }
                    }}
                  >
                    <option value="">Ad-hoc visit (today)</option>
                    {(visitsQuery.data?.results ?? [])
                      .filter((visit) => visit.status === "PLANNED")
                      .map((visit) => (
                        <option key={visit.id} value={visit.id}>
                          {visit.representative_name} · planned{" "}
                          {visit.planned_date ? formatDate(visit.planned_date) : "—"}
                        </option>
                      ))}
                  </Select>
                </Field>
                <Field label="Representative (MR)">
                  <Select
                    value={visitRep}
                    onChange={(e) => setVisitRep(e.target.value)}
                    disabled={Boolean(logTarget)}
                  >
                    <option value="">Select…</option>
                    {repsQuery.data?.results.map((rep) => (
                      <option key={rep.id} value={rep.id}>
                        {rep.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Outcome">
                  <Select value={visitOutcome} onChange={(e) => setVisitOutcome(e.target.value)}>
                    <option value="INTERESTED">Interested</option>
                    <option value="NEUTRAL">Neutral</option>
                    <option value="NOT_INTERESTED">Not interested</option>
                    <option value="PRESCRIBING">Prescribing</option>
                  </Select>
                </Field>
                <Field label="Next visit">
                  <Input
                    type="date"
                    value={visitNext}
                    onChange={(e) => setVisitNext(e.target.value)}
                  />
                </Field>
                <div className="col-span-2">
                  <Field label="Notes">
                    <Input value={visitNotes} onChange={(e) => setVisitNotes(e.target.value)} />
                  </Field>
                </div>
                <Field label="Sample medicine">
                  <Select
                    value={sampleMedicine}
                    onChange={(e) => {
                      setSampleMedicine(e.target.value);
                      setSampleBatch("");
                    }}
                  >
                    <option value="">—</option>
                    {mappingsQuery.data?.map((mapping) => (
                      <option key={mapping.id} value={mapping.medicine}>
                        {mapping.medicine_name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Sample batch (promo stock at branch)">
                  <Select
                    value={sampleBatch}
                    onChange={(e) => setSampleBatch(e.target.value)}
                    disabled={!sampleMedicine}
                  >
                    <option value="">—</option>
                    {batchesQuery.data?.results.map((batch) => (
                      <option key={batch.id} value={batch.id}>
                        {batch.batch_number} · exp{" "}
                        {batch.expiry_date ? formatDate(batch.expiry_date) : "—"}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Sample qty">
                  <Input
                    type="number"
                    step="0.001"
                    min="0.001"
                    value={sampleQty}
                    onChange={(e) => setSampleQty(e.target.value)}
                  />
                </Field>
                <div className="col-span-2">
                  <Button
                    onClick={() => logMutation.mutate()}
                    disabled={logMutation.isPending || !visitBranchId || (!logTarget && !visitRep)}
                  >
                    {logMutation.isPending ? "Saving…" : "Log visit"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

export default function DoctorsPage() {
  const queryClient = useQueryClient();
  const { hasPerm } = useAuth();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editing, setEditing] = useState<Doctor | null>(null);
  const [selected, setSelected] = useState<Doctor | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  const doctorParams = new URLSearchParams({ page_size: "50", page: String(page) });
  if (debouncedSearch) doctorParams.set("search", debouncedSearch);

  const doctorsQuery = useQuery({
    queryKey: ["doctors", debouncedSearch, page],
    queryFn: () => api.get<Paginated<Doctor>>(`/doctors/?${doctorParams.toString()}`),
  });
  const territoriesQuery = useQuery({
    queryKey: ["territories", "select"],
    queryFn: () => api.get<Paginated<Territory>>("/territories/?page_size=100&is_active=true"),
  });

  const payloadFor = (payload: typeof emptyForm) => ({
    ...payload,
    phones: payload.phone ? [payload.phone] : [],
    territory: payload.territory || null,
    registration_no: payload.registration_no || null,
  });

  const createMutation = useMutation({
    meta: { successMessage: "Doctor created" },
    mutationFn: (payload: typeof emptyForm) => api.post<Doctor>("/doctors/", payloadFor(payload)),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["doctors"] });
    },
  });

  const updateMutation = useMutation({
    meta: { successMessage: "Doctor updated" },
    mutationFn: (payload: typeof emptyForm) =>
      api.patch<Doctor>(`/doctors/${editing?.id}/`, payloadFor(payload)),
    onSuccess: () => {
      setForm(emptyForm);
      setEditing(null);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["doctors"] });
    },
  });

  const openEdit = (doctor: Doctor) => {
    setEditing(doctor);
    setForm({
      code: doctor.code,
      name: doctor.name,
      specialty: doctor.specialty,
      category: doctor.category,
      doctor_type: doctor.doctor_type,
      phone: doctor.phones[0] ?? "",
      registration_no: doctor.registration_no ?? "",
      territory: doctor.territory ?? "",
    });
    setShowForm(true);
  };

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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Doctors</h1>
        {hasPerm("DOCTOR_MANAGE") ? (
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
            {showForm ? "Close" : "Add doctor"}
          </Button>
        ) : null}
      </div>

      {selected ? <DoctorPanel doctor={selected} onClose={() => setSelected(null)} /> : null}

      {showForm && hasPerm("DOCTOR_MANAGE") ? (
        <Card>
          <CardHeader
            title={editing ? `Edit ${editing.name}` : "New doctor"}
            subtitle="Promotions are mapped medicine-by-medicine."
          />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error ?? updateMutation.error} />
            </div>
            <Field label="Code" error={fieldError("code")}>
              <Input
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                required
              />
            </Field>
            <Field label="Name" error={fieldError("name")}>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </Field>
            <Field label="Specialty" error={fieldError("specialty")}>
              <Input
                value={form.specialty}
                onChange={(e) => setForm({ ...form, specialty: e.target.value })}
              />
            </Field>
            <Field label="Type" error={fieldError("doctor_type")}>
              <Select
                value={form.doctor_type}
                onChange={(e) => setForm({ ...form, doctor_type: e.target.value })}
              >
                <option value="CONSULTANT">Consultant</option>
                <option value="GP">General practitioner</option>
                <option value="OTHER">Other</option>
              </Select>
            </Field>
            <Field label="Category" error={fieldError("category")}>
              <Select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
              </Select>
            </Field>
            <Field label="Phone" error={fieldError("phones")}>
              <Input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </Field>
            <Field label="Registration no." error={fieldError("registration_no")}>
              <Input
                value={form.registration_no}
                onChange={(e) => setForm({ ...form, registration_no: e.target.value })}
              />
            </Field>
            <Field label="Territory" error={fieldError("territory")}>
              <Select
                value={form.territory}
                onChange={(e) => setForm({ ...form, territory: e.target.value })}
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
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {createMutation.isPending || updateMutation.isPending
                  ? "Saving…"
                  : editing
                    ? "Save changes"
                    : "Create doctor"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Doctor directory"
          subtitle={doctorsQuery.data ? `${doctorsQuery.data.count} doctor(s)` : undefined}
          action={
            <Input
              placeholder="Search name, specialty…"
              aria-label="Search doctors"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-52"
            />
          }
        />
        <ErrorBanner error={doctorsQuery.error} />
        {doctorsQuery.isLoading ? (
          <Spinner />
        ) : !doctorsQuery.data || doctorsQuery.data.results.length === 0 ? (
          <EmptyState message="No doctors yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {doctorsQuery.data.results.map((doctor) => (
              <li key={doctor.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div>
                  <p className="font-medium">
                    {doctor.name}{" "}
                    <span className="font-mono text-xs text-slate-500">{doctor.code}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {doctor.specialty || "—"} · category {doctor.category} ·{" "}
                    {doctor.territory_name || "no territory"} · {doctor.open_mapping_count} promoted
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {doctor.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                  {hasPerm("DOCTOR_MANAGE") ? (
                    <Button size="sm" variant="secondary" onClick={() => openEdit(doctor)}>
                      Edit
                    </Button>
                  ) : null}
                  <Button size="sm" variant="secondary" onClick={() => setSelected(doctor)}>
                    Mappings & visits
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {doctorsQuery.data && doctorsQuery.data.count > 0 ? (
          <Pagination
            page={page}
            hasPrevious={Boolean(doctorsQuery.data.previous)}
            hasNext={Boolean(doctorsQuery.data.next)}
            onChange={setPage}
          />
        ) : null}
      </Card>
    </div>
  );
}
