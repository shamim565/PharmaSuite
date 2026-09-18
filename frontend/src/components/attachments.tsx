"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { Badge, Button, ErrorBanner, Field, Spinner, pushToast } from "@/components/ui";
import { ApiError, api, apiDownload, apiUpload } from "@/lib/api";
import type { AttachmentRow } from "@/lib/types";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AttachmentPanel({
  ownerType,
  ownerId,
  title,
}: {
  ownerType: string;
  ownerId: string;
  title: string;
}) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const attachmentsQuery = useQuery({
    queryKey: ["attachments", ownerType, ownerId],
    queryFn: () =>
      api.get<{ count: number; results: AttachmentRow[] }>(
        `/attachments/?owner_type=${ownerType}&owner_id=${ownerId}`,
      ),
  });

  const uploadMutation = useMutation({
    meta: { successMessage: "File uploaded" },
    mutationFn: (file: File) =>
      apiUpload("/attachments/", file, { owner_type: ownerType, owner_id: ownerId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attachments", ownerType, ownerId] });
      if (fileInput.current) fileInput.current.value = "";
    },
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase text-slate-500">{title}</p>
        <label className="cursor-pointer rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
          Upload file
          <input
            ref={fileInput}
            type="file"
            className="hidden"
            disabled={uploadMutation.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) uploadMutation.mutate(file);
            }}
          />
        </label>
      </div>
      <ErrorBanner error={uploadMutation.error ?? attachmentsQuery.error} />
      {uploadMutation.isPending ? <Spinner label="Uploading…" /> : null}
      {attachmentsQuery.isLoading ? (
        <Spinner />
      ) : !attachmentsQuery.data || attachmentsQuery.data.results.length === 0 ? (
        <p className="text-sm text-slate-500">No files yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {attachmentsQuery.data.results.map((attachment) => (
            <li
              key={attachment.id}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
            >
              <div>
                <p className="font-medium">{attachment.file_name}</p>
                <p className="text-xs text-slate-500">
                  {formatSize(attachment.size_bytes)} · {attachment.uploaded_by_name || "system"}
                </p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  try {
                    await apiDownload(`/attachments/${attachment.id}/download/`, attachment.file_name);
                  } catch (err) {
                    pushToast(err instanceof ApiError ? err.message : "Download failed", "error");
                  }
                }}
              >
                Download
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AttachmentBadge({ count }: { count: number }) {
  if (!count) return null;
  return <Badge tone="slate">{count} file(s)</Badge>;
}