"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

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
  Spinner,
  Tabs,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type {
  FiscalPeriod,
  NotificationPreference,
  NotificationPreferenceList,
  SettingGroups,
} from "@/lib/types";

const TABS = [
  "Company",
  "Approvals",
  "Credit & Expiry",
  "Features",
  "Numbering",
  "Notifications",
  "Fiscal periods",
] as const;
type Tab = (typeof TABS)[number];

const COMPANY_KEYS = [
  "COMPANY_NAME",
  "COMPANY_ADDRESS",
  "COMPANY_PHONE",
  "COMPANY_EMAIL",
  "COMPANY_BIN",
  "COMPANY_VAT_REG",
];
const APPROVAL_KEYS = ["EXPENSE_APPROVAL_THRESHOLD", "STOCK_ADJUSTMENT_APPROVAL_THRESHOLD"];
const CREDIT_KEYS = ["CUSTOMER_OVERDUE_BLOCK_DAYS", "NEAR_EXPIRY_DAYS"];
const FEATURE_KEYS = ["AUTO_APPLY_ADVANCE", "SALES_VAT_ENABLED", "PURCHASE_VAT_ENABLED"];
const BOOLEAN_KEYS = new Set(FEATURE_KEYS);
const NUMBERING_KEYS = [
  "INVOICE_PREFIX",
  "RECEIPT_PREFIX",
  "CREDIT_NOTE_PREFIX",
  "DEBIT_NOTE_PREFIX",
  "PURCHASE_PREFIX",
  "SUPPLIER_PAYMENT_PREFIX",
  "ADJUSTMENT_PREFIX",
  "EXPENSE_PREFIX",
  "INCOME_PREFIX",
  "DOCUMENT_NUMBER_WIDTH",
];
const NOTIFICATION_KEYS = ["SMS_GATEWAY_URL", "SMS_GATEWAY_TOKEN"];

function NotificationsTab() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const prefsQuery = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => api.get<NotificationPreferenceList>("/notifications/preferences/"),
  });

  const saveMutation = useMutation({
    meta: { successMessage: "Notification preferences saved" },
    mutationFn: (rows: NotificationPreference[]) =>
      api.put<NotificationPreferenceList>("/notifications/preferences/", {
        preferences: Object.fromEntries(
          rows.map((row) => [
            row.category,
            {
              enabled: row.enabled,
              email_enabled: row.email_enabled,
              sms_enabled: row.sms_enabled,
            },
          ]),
        ),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notification-preferences"] }),
  });

  const hasEmail = Boolean(user?.email);
  const hasMobile = Boolean(user?.mobile);

  return (
    <Card>
      <CardHeader
        title="Alert delivery channels"
        subtitle={
          hasEmail || hasMobile
            ? `In-app always applies · email ${user?.email ?? "not set"} · SMS ${user?.mobile ?? "not set"}`
            : "Email and SMS channels are unavailable until the user has an email or mobile on record."
        }
      />
      <ErrorBanner error={prefsQuery.error ?? saveMutation.error} />
      {prefsQuery.isLoading ? (
        <Spinner />
      ) : !prefsQuery.data ? (
        <EmptyState message="No notification preferences available." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {prefsQuery.data.results.map((row) => (
            <li
              key={row.category}
              className="flex flex-wrap items-center justify-between gap-3 p-4"
            >
              <p className="text-sm font-medium text-slate-700">{row.label}</p>
              <div className="flex flex-wrap items-center gap-4">
                <label className="flex items-center gap-1.5 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={row.enabled}
                    disabled={saveMutation.isPending}
                    onChange={(e) =>
                      saveMutation.mutate(
                        prefsQuery.data.results.map((item) =>
                          item.category === row.category
                            ? { ...item, enabled: e.target.checked }
                            : item,
                        ),
                      )
                    }
                  />
                  In-app
                </label>
                <label
                  className={`flex items-center gap-1.5 text-sm ${hasEmail ? "text-slate-600" : "text-slate-400"}`}
                >
                  <input
                    type="checkbox"
                    disabled={!hasEmail || saveMutation.isPending}
                    checked={row.email_enabled}
                    onChange={(e) =>
                      saveMutation.mutate(
                        prefsQuery.data.results.map((item) =>
                          item.category === row.category
                            ? { ...item, email_enabled: e.target.checked }
                            : item,
                        ),
                      )
                    }
                  />
                  Email
                </label>
                <label
                  className={`flex items-center gap-1.5 text-sm ${hasMobile ? "text-slate-600" : "text-slate-400"}`}
                >
                  <input
                    type="checkbox"
                    disabled={!hasMobile || saveMutation.isPending}
                    checked={row.sms_enabled}
                    onChange={(e) =>
                      saveMutation.mutate(
                        prefsQuery.data.results.map((item) =>
                          item.category === row.category
                            ? { ...item, sms_enabled: e.target.checked }
                            : item,
                        ),
                      )
                    }
                  />
                  SMS
                </label>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SettingsSection({
  title,
  subtitle,
  keys,
  form,
  setForm,
}: {
  title: string;
  subtitle: string;
  keys: string[];
  form: Record<string, string>;
  setForm: (value: Record<string, string>) => void;
}) {
  const queryClient = useQueryClient();
  const [baseline, setBaseline] = useState<Record<string, string> | null>(null);

  useEffect(() => {
    if (baseline === null && keys.every((key) => key in form)) {
      setBaseline(Object.fromEntries(keys.map((key) => [key, form[key] ?? ""])));
    }
  }, [form, keys, baseline]);

  const dirty =
    baseline !== null && keys.some((key) => (form[key] ?? "") !== (baseline[key] ?? ""));

  const saveMutation = useMutation({
    meta: { successMessage: "Settings saved" },
    mutationFn: () => api.put<SettingGroups>("/settings/", form),
    onSuccess: () => {
      setBaseline(Object.fromEntries(keys.map((key) => [key, form[key] ?? ""])));
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const labels: Record<string, string> = {
    COMPANY_NAME: "Company name",
    COMPANY_ADDRESS: "Address",
    COMPANY_PHONE: "Phone",
    COMPANY_EMAIL: "Email",
    COMPANY_BIN: "BIN number",
    COMPANY_VAT_REG: "VAT registration",
    EXPENSE_APPROVAL_THRESHOLD: "Expense approval threshold (BDT)",
    STOCK_ADJUSTMENT_APPROVAL_THRESHOLD: "Stock adjustment approval threshold (BDT)",
    CUSTOMER_OVERDUE_BLOCK_DAYS: "Customer overdue block days",
    NEAR_EXPIRY_DAYS: "Near-expiry warning days",
    AUTO_APPLY_ADVANCE: "Auto-apply customer advance at sale confirmation",
    SALES_VAT_ENABLED: "Charge VAT on sales invoices",
    PURCHASE_VAT_ENABLED: "Charge VAT on purchases",
    DOCUMENT_NUMBER_WIDTH: "Document number width",
  };

  return (
    <Card>
      <CardHeader title={title} subtitle={subtitle} />
      <div className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
        <ErrorBanner error={saveMutation.error} />
        {keys.map((key) =>
          BOOLEAN_KEYS.has(key) ? (
            <label key={key} className="col-span-2 flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form[key] === "true" || form[key] === "True"}
                onChange={(e) => setForm({ ...form, [key]: e.target.checked ? "true" : "false" })}
              />
              {labels[key]}
            </label>
          ) : (
            <Field key={key} label={labels[key] ?? key}>
              <Input
                value={form[key] ?? ""}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            </Field>
          ),
        )}
        <div className="col-span-2 flex items-center gap-3 lg:col-span-4">
          <Button
            size="sm"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !dirty}
          >
            {saveMutation.isPending ? "Saving…" : "Save"}
          </Button>
          {dirty ? <span className="text-xs text-amber-700">Unsaved changes</span> : null}
        </div>
      </div>
    </Card>
  );
}

export default function SettingsPage() {
  const { hasPerm } = useAuth();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("Company");
  const [form, setForm] = useState<Record<string, string>>({});
  const [periodFor, setPeriodFor] = useState<FiscalPeriod | null>(null);
  const [reason, setReason] = useState("");

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<SettingGroups>("/settings/"),
  });
  const periodsQuery = useQuery({
    queryKey: ["fiscal-periods"],
    queryFn: () => api.get<{ count: number; results: FiscalPeriod[] }>("/periods/"),
  });

  useEffect(() => {
    if (settingsQuery.data) {
      const flat: Record<string, string> = {};
      for (const group of Object.values(settingsQuery.data.groups)) {
        for (const [key, value] of Object.entries(group)) {
          flat[key] = String(value);
        }
      }
      setForm(flat);
    }
  }, [settingsQuery.data]);

  const periodMutation = useMutation({
    meta: {
      successMessage: (variables: { action: string }) =>
        variables.action === "lock" ? "Period locked" : "Period unlocked",
    },
    mutationFn: ({ period, action }: { period: FiscalPeriod; action: "lock" | "unlock" }) =>
      api.post(`/periods/${period.id}/${action}/`, { reason }),
    onSuccess: () => {
      setPeriodFor(null);
      setReason("");
      queryClient.invalidateQueries({ queryKey: ["fiscal-periods"] });
    },
  });

  if (!hasPerm("SETTINGS_VIEW")) {
    return (
      <Card>
        <EmptyState message="You need SETTINGS_VIEW to open this page." />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-800">Settings</h1>

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {settingsQuery.isLoading ? <Spinner /> : null}
      {settingsQuery.error ? <ErrorBanner error={settingsQuery.error} /> : null}

      {tab === "Company" ? (
        <SettingsSection
          title="Company profile"
          subtitle="Used on documents and reports."
          keys={COMPANY_KEYS}
          form={form}
          setForm={setForm}
        />
      ) : null}
      {tab === "Approvals" ? (
        <SettingsSection
          title="Approval thresholds"
          subtitle="Documents above these amounts require dual-control approval."
          keys={APPROVAL_KEYS}
          form={form}
          setForm={setForm}
        />
      ) : null}
      {tab === "Credit & Expiry" ? (
        <SettingsSection
          title="Credit policy & expiry"
          subtitle="Overdue blocking and expiry alert windows."
          keys={CREDIT_KEYS}
          form={form}
          setForm={setForm}
        />
      ) : null}
      {tab === "Features" ? (
        <SettingsSection
          title="Feature flags"
          subtitle="Behavioural switches."
          keys={FEATURE_KEYS}
          form={form}
          setForm={setForm}
        />
      ) : null}
      {tab === "Numbering" ? (
        <SettingsSection
          title="Document numbering"
          subtitle="Prefixes apply to new fiscal years/branches; existing documents keep their numbers."
          keys={NUMBERING_KEYS}
          form={form}
          setForm={setForm}
        />
      ) : null}

      {tab === "Notifications" ? (
        <>
          <NotificationsTab />
          {hasPerm("SETTINGS_MANAGE") ? (
            <SettingsSection
              title="SMS gateway"
              subtitle="JSON POST gateway receiving {to, text}. Leave URL empty to disable SMS delivery."
              keys={NOTIFICATION_KEYS}
              form={form}
              setForm={setForm}
            />
          ) : null}
        </>
      ) : null}

      {tab === "Fiscal periods" ? (
        <>
          {periodFor ? (
            <Card>
              <CardHeader
                title={`${periodFor.status === "LOCKED" ? "Unlock" : "Lock"} ${formatDate(periodFor.start_date)} → ${formatDate(periodFor.end_date)}`}
                action={
                  <Button size="sm" variant="secondary" onClick={() => setPeriodFor(null)}>
                    Cancel
                  </Button>
                }
              />
              <div className="space-y-3 p-4">
                {periodFor.checklist ? (
                  <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
                    Pending expenses: {periodFor.checklist.pending_expenses} · pending adjustments:{" "}
                    {periodFor.checklist.pending_adjustments} — {periodFor.checklist.note}
                  </p>
                ) : null}
                <ErrorBanner error={periodMutation.error} />
                <Field label="Reason">
                  <Input value={reason} onChange={(e) => setReason(e.target.value)} />
                </Field>
                <Button
                  variant={periodFor.status === "LOCKED" ? "secondary" : "danger"}
                  onClick={() =>
                    periodMutation.mutate({
                      period: periodFor,
                      action: periodFor.status === "LOCKED" ? "unlock" : "lock",
                    })
                  }
                  disabled={periodMutation.isPending || !reason}
                >
                  {periodFor.status === "LOCKED" ? "Unlock period" : "Lock period"}
                </Button>
              </div>
            </Card>
          ) : null}

          <Card>
            <CardHeader
              title="Fiscal months (July–June)"
              subtitle={periodsQuery.data ? `${periodsQuery.data.count} period(s)` : undefined}
            />
            <ErrorBanner error={periodsQuery.error} />
            {periodsQuery.isLoading ? (
              <Spinner />
            ) : !periodsQuery.data || periodsQuery.data.results.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">No fiscal periods yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {periodsQuery.data.results.map((period) => (
                  <li
                    key={period.id}
                    className="flex flex-wrap items-center justify-between gap-2 p-4"
                  >
                    <div>
                      <p className="font-medium">
                        {formatDate(period.start_date)} → {formatDate(period.end_date)}
                      </p>
                      <p className="text-xs text-slate-500">
                        FY {period.fiscal_year}-{period.fiscal_year + 1} · month{" "}
                        {period.period_month}
                        {period.lock_reason ? ` · locked: ${period.lock_reason}` : ""}
                        {period.unlock_reason ? ` · reopened: ${period.unlock_reason}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {period.status === "LOCKED" ? (
                        <Badge tone="rose">Locked</Badge>
                      ) : (
                        <Badge tone="green">Open</Badge>
                      )}
                      {hasPerm("PERIOD_LOCK") ? (
                        <Button size="sm" variant="secondary" onClick={() => setPeriodFor(period)}>
                          {period.status === "LOCKED" ? "Unlock" : "Lock"}
                        </Button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}
