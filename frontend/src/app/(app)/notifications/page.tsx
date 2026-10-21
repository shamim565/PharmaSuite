"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { NotificationList, NotificationPreferenceList } from "@/lib/types";

function severityTone(severity: string): "green" | "amber" | "rose" | "slate" {
  if (severity === "CRITICAL") return "rose";
  if (severity === "WARNING") return "amber";
  if (severity === "INFO") return "green";
  return "slate";
}

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [unreadOnly, setUnreadOnly] = useState(false);

  const params = new URLSearchParams({ page_size: "100" });
  if (unreadOnly) params.set("unread_only", "true");

  const notificationsQuery = useQuery({
    queryKey: ["notifications", unreadOnly],
    queryFn: () => api.get<NotificationList>(`/notifications/?${params.toString()}`),
  });

  const readAllMutation = useMutation({
    meta: { successMessage: "All notifications marked read" },
    mutationFn: () => api.post("/notifications/read-all/", {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  const readMutation = useMutation({
    mutationFn: (id: string) => api.post(`/notifications/${id}/read/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  const preferencesQuery = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => api.get<NotificationPreferenceList>("/notifications/preferences/"),
  });

  const preferenceMutation = useMutation({
    mutationFn: (preferences: Record<string, boolean>) =>
      api.put<NotificationPreferenceList>("/notifications/preferences/", { preferences }),
    onSuccess: (data) => queryClient.setQueryData(["notification-preferences"], data),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Notifications</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => setUnreadOnly(e.target.checked)}
            />
            Unread only
          </label>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => readAllMutation.mutate()}
            disabled={
              readAllMutation.isPending || (notificationsQuery.data?.unread_count ?? 0) === 0
            }
          >
            Mark all read
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader
          title="Alert preferences"
          subtitle="Choose which automated alerts you receive."
        />
        <ErrorBanner error={preferencesQuery.error ?? preferenceMutation.error} />
        {preferencesQuery.isLoading ? (
          <Spinner />
        ) : (
          <div className="grid grid-cols-2 gap-2 p-4 lg:grid-cols-3">
            {preferencesQuery.data?.results.map((preference) => (
              <label
                key={preference.category}
                className="flex items-center gap-2 text-sm text-slate-700"
              >
                <input
                  type="checkbox"
                  checked={preference.enabled}
                  disabled={preferenceMutation.isPending}
                  onChange={(event) =>
                    preferenceMutation.mutate({ [preference.category]: event.target.checked })
                  }
                />
                {preference.label}
              </label>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="All notifications"
          subtitle={
            notificationsQuery.data ? `${notificationsQuery.data.unread_count} unread` : undefined
          }
        />
        <ErrorBanner error={notificationsQuery.error} />
        {notificationsQuery.isLoading ? (
          <Spinner />
        ) : !notificationsQuery.data || notificationsQuery.data.results.length === 0 ? (
          <EmptyState message="No notifications yet." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {notificationsQuery.data.results.map((item) => (
              <li key={item.id} className={`p-4 ${item.is_read ? "opacity-60" : ""}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium">
                      <Badge tone={severityTone(item.severity)}>{item.type}</Badge> {item.title}
                    </p>
                    {item.body ? <p className="text-xs text-slate-500">{item.body}</p> : null}
                    <p className="text-xs text-slate-500">{formatDateTime(item.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {!item.is_read ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => readMutation.mutate(item.id)}
                      >
                        Mark read
                      </Button>
                    ) : null}
                    {item.deep_link ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          if (!item.is_read) readMutation.mutate(item.id);
                          router.push(item.deep_link);
                        }}
                      >
                        Open
                      </Button>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
