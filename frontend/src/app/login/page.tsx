"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/app/providers";
import { Button, ErrorBanner, Field, Input } from "@/components/ui";
import { login, loginMfa } from "@/lib/api";

export default function LoginPage() {
  const { user, loading, setUser } = useAuth();
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await login(identifier.trim(), password);
      if (result.mfa_required) {
        setMfaToken(result.mfa_token);
        return;
      }
      setUser(result.user);
      router.replace("/");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  const onVerify = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const current = await loginMfa(mfaToken, mfaCode.trim());
      setUser(current);
      router.replace("/");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-bold text-primary-700">PharmaSuite</h1>
          <p className="text-sm text-slate-500">
            {mfaToken ? "Enter your authenticator code" : "Sign in to continue"}
          </p>
        </div>

        {mfaToken ? (
          <form
            onSubmit={onVerify}
            className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <ErrorBanner error={error} />
            <Field label="6-digit code">
              <Input
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                placeholder="123456"
                inputMode="numeric"
                autoComplete="one-time-code"
                autoFocus
                required
              />
            </Field>
            <Button type="submit" className="w-full" disabled={submitting || mfaCode.trim().length < 6}>
              {submitting ? "Verifying…" : "Verify and sign in"}
            </Button>
            <button
              type="button"
              className="w-full text-center text-xs text-slate-500 hover:underline"
              onClick={() => {
                setMfaToken("");
                setMfaCode("");
                setError(null);
              }}
            >
              Back to password
            </button>
          </form>
        ) : (
          <form
            onSubmit={onSubmit}
            className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <ErrorBanner error={error} />
            <Field label="Mobile or email">
              <Input
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="01700000000"
                autoComplete="username"
                required
              />
            </Field>
            <Field label="Password">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </Field>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-center text-xs text-slate-500">
              Default owner: 01700000000 / Admin@1234
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
