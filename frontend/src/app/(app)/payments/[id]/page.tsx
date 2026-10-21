"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge, Button, ErrorBanner, Spinner, pushToast } from "@/components/ui";
import { ApiError, api, apiDownload } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type { CustomerPayment } from "@/lib/types";

const METHOD_LABEL: Record<string, string> = {
  CASH: "Cash",
  BANK: "Bank",
  MFS: "MFS",
  CHEQUE: "Cheque",
};

export default function ReceiptDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["receipt", params.id],
    queryFn: () => api.get<CustomerPayment>(`/payments/${params.id}/`),
  });

  if (isLoading) return <Spinner label="Loading receipt…" />;

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap items-center justify-between gap-2">
        <Link href="/payments">
          <Button size="sm" variant="secondary">
            <ArrowLeft aria-hidden size={14} />
            Back to payments
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={!data}
            onClick={async () => {
              if (!data) return;
              try {
                await apiDownload(`/payments/${data.id}/print/`, `${data.number ?? "receipt"}.pdf`);
              } catch (err) {
                pushToast(err instanceof ApiError ? err.message : "Download failed", "error");
              }
            }}
          >
            Download PDF
          </Button>
          <Button size="sm" onClick={() => window.print()} disabled={!data}>
            Print (A4)
          </Button>
        </div>
      </div>

      <ErrorBanner error={error} />

      {data ? (
        <div className="print-container mx-auto max-w-2xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between border-b border-slate-200 pb-4">
            <div>
              <h1 className="text-lg font-bold text-slate-900">PharmaSuite</h1>
              <p className="text-sm text-slate-600">{data.branch_name}</p>
            </div>
            <div className="text-right">
              <h2 className="text-base font-semibold uppercase tracking-wide text-slate-700">
                Money Receipt
              </h2>
              <p className="font-mono text-sm">{data.number}</p>
              <p className="text-xs text-slate-500">Date: {formatDate(data.business_date)}</p>
              <div className="mt-1">
                {data.status === "ACTIVE" ? (
                  <Badge tone="green">Active</Badge>
                ) : (
                  <Badge tone="rose">Reversed</Badge>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 py-4 text-sm">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Received from</p>
              <p className="font-medium">{data.customer_name}</p>
            </div>
            <div className="text-right text-xs text-slate-500">
              <p>Method: {METHOD_LABEL[data.method] ?? data.method}</p>
              <p>Account: {data.account_name}</p>
              {data.reference ? <p>Reference: {data.reference}</p> : null}
              {data.collector_name ? <p>Collected by: {data.collector_name}</p> : null}
            </div>
          </div>

          <div className="rounded-lg bg-slate-50 p-4 text-center">
            <p className="text-xs uppercase text-slate-500">Amount received</p>
            <p className="text-2xl font-bold text-slate-900">{formatMoney(data.amount)}</p>
          </div>

          {data.allocations.length > 0 ? (
            <table className="mt-4 w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="py-2">Applied to invoice</th>
                  <th className="py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.allocations.map((allocation) => (
                  <tr key={allocation.id}>
                    <td className="py-2 font-mono text-xs">
                      <Link
                        href={`/sales/${allocation.invoice}`}
                        className="text-primary-700 hover:underline"
                      >
                        {allocation.invoice_number ?? allocation.invoice}
                      </Link>
                    </td>
                    <td className="py-2 text-right">{formatMoney(allocation.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="mt-4 text-center text-xs text-slate-500">
              Held as advance on account (not allocated to an invoice).
            </p>
          )}

          <div className="mt-10 grid grid-cols-2 gap-8 border-t border-slate-200 pt-6 text-xs text-slate-500">
            <div>
              <div className="border-t border-slate-400 pt-1">Received by</div>
            </div>
            <div>
              <div className="border-t border-slate-400 pt-1 text-right">Authorised signature</div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
