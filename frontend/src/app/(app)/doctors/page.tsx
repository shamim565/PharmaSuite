"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Select, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
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

function DoctorPanel({ doctor, onClose }: { doctor: Doctor; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [mappingMedicine, setMappingMedicine] = useState("");
  const [mappingPriority, setMappingPriority] = useState("HIGH");
  const [visitRep, setVisitRep] = useState("");
  const [visitPurpose, setVisitPurpose] = useState("");
  const [visitOutcome, setVisitOutcome] = useState("INTERESTED");
  const [visitNotes, setVisitNotes] = useState("");
  const [visitNext, setVisitNext] = useState("");
  const [sampleMedicine, setSampleMedicine] = useState("");
  const [sampleBatch, setSampleBatch] = useState("");
  const [sampleQty, setSampleQty] = useState("");

  const mappingsQuery = useQuery({
    queryKey: ["doctor-mappings", doctor.id],
    queryFn: () => api.get<DoctorMedicine[]>(`/doctors/${doctor.id}/medicines/`),
  });
  const visitsQuery = useQuery({
    queryKey: ["doctor-visits", doctor.id],
    queryFn: () => api.get<Paginated<DoctorVisit>>(`/doctor-visits/?doctor=${doctor.id}&page_size=20`),
  });
  const medicinesQuery = useQuery({
    queryKey: ["medicines", "select"],
    queryFn: () => api.get<Paginated<Medicine>>("/medicines/?page_size=200&is_active=true"),
  });
  const repsQuery = useQuery({
    queryKey: ["reps", "medical"],
    queryFn: () => api.get<Paginated<Representative>>("/representatives/?page_size=100&is_active=true&rep_type=MEDICAL"),
  });
  const batchesQuery = useQuery({
    queryKey: ["batches", "sample", sampleMedicine],
    queryFn: () => api.get<Paginated<MedicineBatch>>(`/batches/?page_size=100&medicine=${sampleMedicine}`),
    enabled: Boolean(sampleMedicine),
  });

  const [chamberForm, setChamberForm] = useState({ name: "", address: "", visiting_hours: "" });

  const chambersQuery = useQuery({
    queryKey: ["doctor-chambers", doctor.id],
    queryFn: () => api.get<{ count: number; results: DoctorChamber[] }>(`/doctors/${doctor.id}/chambers/`),
  });

  const chamberMutation = useMutation({
    mutationFn: () => api.post(`/doctors/${doctor.id}/chambers/`, chamberForm),
    onSuccess: () => {
      setChamberForm({ name: "", address: "", visiting_hours: "" });
      queryClient.invalidateQueries({ queryKey: ["doctor-chambers", doctor.id] });
    },
  });

  const deleteChamberMutation = useMutation({
    mutationFn: (chamber: DoctorChamber) => api.delete(`/doctors/${doctor.id}/chambers/${chamber.id}/`),
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
    mutationFn: () => api.post(`/doctors/${doctor.id}/medicines/`, { medicine: mappingMedicine, priority: mappingPriority }),
    onSuccess: () => {
      setMappingMedicine("");
      invalidate();
    },
  });
  const endMappingMutation = useMutation({
    mutationFn: (mapping: DoctorMedicine) => api.post(`/doctor-medicines/${mapping.id}/end/`),
    onSuccess: () => invalidate(),
  });

  const visitMutation = useMutation({
    mutationFn: async () => {
      const now = new Date();
      const isoDate = now.toISOString().slice(0, 10);
      const created = await api.post<DoctorVisit>("/doctor-visits/", {
        doctor: doctor.id,
        representative: visitRep,
        branch: (await api.get<Paginated<Branch>>("/branches/?page_size=1")).results[0]?.id,
        planned_date: isoDate,
        purpose: visitPurpose,
      });
      const payload: Record<string, unknown> = {
        outcome: visitOutcome,
        products_discussed: mappingsQuery.data?.map((m) => m.medicine) ?? [],
        notes: visitNotes,
        next_visit_date: visitNext || null,
      };
      if (sampleMedicine && sampleBatch && sampleQty) {
        payload.samples = [{ medicine: sampleMedicine, batch: sampleBatch, qty: sampleQty }];
      }
      return api.post(`/doctor-visits/${created.id}/complete/`, payload);
    },
    onSuccess: () => {
      setVisitPurpose("");
      setVisitNotes("");
      setVisitNext("");
      setSampleMedicine("");
      setSampleBatch("");
      setSampleQty("");
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
                <li key={mapping.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <div>
                    <p className="font-medium">{mapping.medicine_name}</p>
                    <p className="text-xs text-slate-500">
                      {mapping.medicine_code} · {mapping.priority || "—"} · since {mapping.effective_from}
                    </p>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => endMappingMutation.mutate(mapping)}>
                    End
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <div className="w-48">
              <Field label="Medicine">
                <Select value={mappingMedicine} onChange={(e) => setMappingMedicine(e.target.value)}>
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
                <Select value={mappingPriority} onChange={(e) => setMappingPriority(e.target.value)}>
                  <option value="HIGH">High</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="LOW">Low</option>
                </Select>
              </Field>
            </div>
            <Button size="sm" onClick={() => mappingMutation.mutate()} disabled={!mappingMedicine || mappingMutation.isPending}>
              Add mapping
            </Button>
          </div>
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
                <li key={chamber.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <div>
                    <p className="font-medium">{chamber.name}</p>
                    <p className="text-xs text-slate-500">
                      {chamber.address || "—"}
                      {chamber.visiting_hours ? ` · ${chamber.visiting_hours}` : ""}
                    </p>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => deleteChamberMutation.mutate(chamber)}>
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <div className="w-40">
              <Field label="Chamber name">
                <Input value={chamberForm.name} onChange={(e) => setChamberForm({ ...chamberForm, name: e.target.value })} />
              </Field>
            </div>
            <div className="w-48">
              <Field label="Address">
                <Input value={chamberForm.address} onChange={(e) => setChamberForm({ ...chamberForm, address: e.target.value })} />
              </Field>
            </div>
            <div className="w-36">
              <Field label="Visiting hours">
                <Input value={chamberForm.visiting_hours} onChange={(e) => setChamberForm({ ...chamberForm, visiting_hours: e.target.value })} />
              </Field>
            </div>
            <Button size="sm" onClick={() => chamberMutation.mutate()} disabled={!chamberForm.name || chamberMutation.isPending}>
              Add chamber
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Visit history</p>
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
                    <Badge tone={visit.status === "COMPLETED" ? "green" : visit.status === "MISSED" ? "rose" : "amber"}>
                      {visit.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    {visit.visited_at?.slice(0, 10) ?? visit.planned_date} · {visit.outcome || visit.missed_reason || "—"}
                    {visit.next_visit_date ? ` · next ${visit.next_visit_date}` : ""}
                  </p>
                  {visit.samples.length > 0 ? (
                    <p className="text-xs text-emerald-700">
                      Samples: {visit.samples.map((sample) => `${sample.medicine_name} ×${sample.qty}`).join(", ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-3 rounded-lg border border-slate-200 p-3 lg:col-span-2">
          <p className="text-xs font-semibold uppercase text-slate-500">Log a completed visit</p>
          <ErrorBanner error={visitMutation.error} />
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
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
            <Field label="Purpose">
              <Input value={visitPurpose} onChange={(e) => setVisitPurpose(e.target.value)} />
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
              <Input type="date" value={visitNext} onChange={(e) => setVisitNext(e.target.value)} />
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
            <Field label="Sample batch (promo stock)">
              <Select value={sampleBatch} onChange={(e) => setSampleBatch(e.target.value)} disabled={!sampleMedicine}>
                <option value="">—</option>
                {batchesQuery.data?.results.map((batch) => (
                  <option key={batch.id} value={batch.id}>
                    {batch.batch_number} · promo via balance
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Sample qty">
              <Input type="number" step="1" min="1" value={sampleQty} onChange={(e) => setSampleQty(e.target.value)} />
            </Field>
            <div className="col-span-2 flex items-end lg:col-span-4">
              <Button
                onClick={() => visitMutation.mutate()}
                disabled={visitMutation.isPending || !visitRep}
              >
                {visitMutation.isPending ? "Saving…" : "Log visit"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function DoctorsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [selected, setSelected] = useState<Doctor | null>(null);

  const doctorsQuery = useQuery({
    queryKey: ["doctors", search],
    queryFn: () => api.get<Paginated<Doctor>>(`/doctors/?page_size=50&search=${encodeURIComponent(search)}`),
  });
  const territoriesQuery = useQuery({
    queryKey: ["territories", "select"],
    queryFn: () => api.get<Paginated<Territory>>("/territories/?page_size=100&is_active=true"),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof emptyForm) =>
      api.post<Doctor>("/doctors/", {
        ...payload,
        phones: payload.phone ? [payload.phone] : [],
        territory: payload.territory || null,
        registration_no: payload.registration_no || null,
      }),
    onSuccess: () => {
      setForm(emptyForm);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["doctors"] });
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    createMutation.mutate(form);
  };

  const fieldError = (name: string): string | null => {
    const err = createMutation.error;
    if (err instanceof ApiError && err.fieldErrors?.[name]) return err.fieldErrors[name][0];
    return null;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Doctors</h1>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Close" : "Add doctor"}
        </Button>
      </div>

      {selected ? <DoctorPanel doctor={selected} onClose={() => setSelected(null)} /> : null}

      {showForm ? (
        <Card>
          <CardHeader title="New doctor" subtitle="Promotions are mapped medicine-by-medicine." />
          <form onSubmit={onSubmit} className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
            <div className="col-span-2 lg:col-span-4">
              <ErrorBanner error={createMutation.error} />
            </div>
            <Field label="Code" error={fieldError("code")}>
              <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
            </Field>
            <Field label="Name" error={fieldError("name")}>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Specialty" error={fieldError("specialty")}>
              <Input value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} />
            </Field>
            <Field label="Type" error={fieldError("doctor_type")}>
              <Select value={form.doctor_type} onChange={(e) => setForm({ ...form, doctor_type: e.target.value })}>
                <option value="CONSULTANT">Consultant</option>
                <option value="GP">General practitioner</option>
                <option value="OTHER">Other</option>
              </Select>
            </Field>
            <Field label="Category" error={fieldError("category")}>
              <Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
              </Select>
            </Field>
            <Field label="Phone" error={fieldError("phones")}>
              <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="Registration no." error={fieldError("registration_no")}>
              <Input
                value={form.registration_no}
                onChange={(e) => setForm({ ...form, registration_no: e.target.value })}
              />
            </Field>
            <Field label="Territory" error={fieldError("territory")}>
              <Select value={form.territory} onChange={(e) => setForm({ ...form, territory: e.target.value })}>
                <option value="">—</option>
                {territoriesQuery.data?.results.map((territory) => (
                  <option key={territory.id} value={territory.id}>
                    {territory.name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="col-span-2 lg:col-span-4">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Create doctor"}
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
              value={search}
              onChange={(e) => setSearch(e.target.value)}
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
                    {doctor.name} <span className="font-mono text-xs text-slate-400">{doctor.code}</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {doctor.specialty || "—"} · category {doctor.category} · {doctor.territory_name || "no territory"} ·{" "}
                    {doctor.open_mapping_count} promoted
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {doctor.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                  <Button size="sm" variant="secondary" onClick={() => setSelected(doctor)}>
                    Mappings & visits
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
