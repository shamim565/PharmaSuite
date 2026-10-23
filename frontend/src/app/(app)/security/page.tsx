"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useAuth } from "@/app/providers";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorBanner,
  Field,
  Input,
  Spinner,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { CurrentUser, UserSession } from "@/lib/types";

export default function SecurityPage() {
  const { user, setUser } = useAuth();
  const [secret, setSecret] = useState<string | null>(null);
  const [provisioningUri, setProvisioningUri] = useState("");
  const [enableCode, setEnableCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [copied, setCopied] = useState(false);

  const refreshUser = async () => {
    const me = await api.get<CurrentUser>("/auth/me/");
    setUser(me);
  };

  const setupMutation = useMutation({
    meta: { successMessage: "2FA setup started" },
    mutationFn: () =>
      api.post<{ secret: string; provisioning_uri: string }>("/auth/me/2fa/setup/", {}),
    onSuccess: (data) => {
      setSecret(data.secret);
      setProvisioningUri(data.provisioning_uri);
    },
  });

  const enableMutation = useMutation({
    meta: { successMessage: "Two-factor enabled" },
    mutationFn: () => api.post("/auth/me/2fa/enable/", { code: enableCode }),
    onSuccess: async () => {
      setSecret(null);
      setProvisioningUri("");
      setEnableCode("");
      await refreshUser();
    },
  });

  const disableMutation = useMutation({
    meta: { successMessage: "Two-factor disabled" },
    mutationFn: () => api.post("/auth/me/2fa/disable/", { code: disableCode }),
    onSuccess: async () => {
      setDisableCode("");
      await refreshUser();
    },
  });

  if (!user) return <Spinner />;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-800">Security</h1>

      <Card>
        <CardHeader
          title="Two-factor authentication (TOTP)"
          subtitle="Time-based codes from Google Authenticator, Authy or any TOTP app."
          action={
            user.totp_enabled ? (
              <Badge tone="green">Enabled</Badge>
            ) : (
              <Badge tone="slate">Disabled</Badge>
            )
          }
        />

        {!user.totp_enabled ? (
          <div className="space-y-3 p-4">
            <ErrorBanner error={setupMutation.error ?? enableMutation.error} />
            {!secret ? (
              <>
                <p className="text-sm text-slate-600">
                  Add a second step to your sign-in. You will need an authenticator app.
                </p>
                <Button
                  size="sm"
                  onClick={() => setupMutation.mutate()}
                  disabled={setupMutation.isPending}
                >
                  {setupMutation.isPending ? "Preparing…" : "Set up two-factor"}
                </Button>
              </>
            ) : (
              <>
                <p className="text-sm text-slate-600">
                  Add this key to your authenticator app (manual entry), then enter the generated
                  code.
                </p>
                <div className="space-y-1 rounded-lg bg-slate-50 p-3">
                  <p className="font-mono text-sm tracking-widest text-slate-800">{secret}</p>
                  <p className="break-all font-mono text-[11px] text-slate-500">
                    {provisioningUri}
                  </p>
                  <button
                    type="button"
                    className="text-xs text-primary-700 hover:underline"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(secret);
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      } catch {
                        // clipboard unavailable (e.g. insecure context) — the key stays selectable
                      }
                    }}
                  >
                    {copied ? "Copied" : "Copy key"}
                  </button>
                </div>
                <Field label="Authenticator code">
                  <Input
                    value={enableCode}
                    onChange={(e) => setEnableCode(e.target.value)}
                    placeholder="123456"
                    inputMode="numeric"
                  />
                </Field>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={enableMutation.isPending || enableCode.trim().length < 6}
                    onClick={() => enableMutation.mutate()}
                  >
                    {enableMutation.isPending ? "Verifying…" : "Enable two-factor"}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setSecret(null);
                      setProvisioningUri("");
                      setEnableCode("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-3 p-4">
            <ErrorBanner error={disableMutation.error} />
            <p className="text-sm text-slate-600">
              Two-factor is active. Enter a current code to turn it off. If you lose your device,
              ask an administrator to reset it.
            </p>
            <Field label="Authenticator code">
              <Input
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
                placeholder="123456"
                inputMode="numeric"
              />
            </Field>
            <Button
              size="sm"
              variant="danger"
              disabled={disableMutation.isPending || disableCode.trim().length < 6}
              onClick={() => disableMutation.mutate()}
            >
              {disableMutation.isPending ? "Disabling…" : "Disable two-factor"}
            </Button>
          </div>
        )}
      </Card>

      <SessionsCard />
    </div>
  );
}

function SessionsCard() {
  const queryClient = useQueryClient();
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.get<{ count: number; results: UserSession[] }>("/auth/sessions/"),
  });
  const revoke = useMutation({
    meta: { successMessage: "Session revoked" },
    mutationFn: (sid: string) => api.delete(`/auth/sessions/${sid}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
  const revokeAll = useMutation({
    meta: { successMessage: "Other sessions revoked" },
    mutationFn: () => api.post("/auth/sessions/revoke-all/", {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });

  const rows = sessions.data?.results ?? [];

  return (
    <Card>
      <CardHeader
        title="Active sessions"
        subtitle="Devices signed in to your account. Revoke anything you do not recognise."
      />
      <div className="space-y-3 p-4">
        <ErrorBanner error={sessions.error ?? revoke.error ?? revokeAll.error} />
        {sessions.isLoading ? (
          <Spinner />
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-500">No sessions found.</p>
        ) : (
          <ul className="space-y-2">
            {rows.map((session) => (
              <li
                key={session.sid}
                className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2 last:border-0"
              >
                <div>
                  <p className="text-sm text-slate-700">
                    {session.user_agent || "Unknown device"}{" "}
                    {session.current ? <Badge tone="green">This device</Badge> : null}
                    {session.revoked_at ? <Badge tone="slate">Revoked</Badge> : null}
                  </p>
                  <p className="text-xs text-slate-500">
                    {session.ip || "unknown IP"} · last seen {formatDateTime(session.last_seen_at)}
                  </p>
                </div>
                {!session.current && !session.revoked_at ? (
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={revoke.isPending}
                    onClick={() => revoke.mutate(session.sid)}
                  >
                    Revoke
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <Button
          size="sm"
          variant="secondary"
          disabled={revokeAll.isPending}
          onClick={() => revokeAll.mutate()}
        >
          {revokeAll.isPending ? "Revoking…" : "Revoke all other sessions"}
        </Button>
      </div>
    </Card>
  );
}
