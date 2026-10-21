"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge, Button, ErrorBanner, Spinner } from "@/components/ui";
import { api, apiDownload } from "@/lib/api";
import { formatDate, formatDateTime, formatMoney, formatQty } from "@/lib/format";
import type { SalesInvoice } from "@/lib/types";

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["invoice", params.id],
    queryFn: () => api.get<SalesInvoice>(`/sales/${params.id}/`),
  });

  if (isLoading) return <Spinner label="Loading invoice…" />;

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap items-center justify-between gap-2">
        <Link href="/sales">
          <Button size="sm" variant="secondary">
            <ArrowLeft aria-hidden size={14} />
            Back to sales
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={!data}
            onClick={() =>
              data && apiDownload(`/sales/${data.id}/print/`, `${data.number ?? "invoice"}.pdf`)
            }
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
        <div className="print-container rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
            <div>
              <h1 className="text-xl font-bold text-slate-900">PharmaSuite</h1>
              <p className="text-sm text-slate-600">{data.branch_name}</p>
              <p className="text-xs text-slate-500">
                {data.branch_address}
                {data.branch_phone ? ` · ${data.branch_phone}` : ""}
              </p>
            </div>
            <div className="text-right">
              <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">
                Invoice
              </h2>
              <p className="font-mono text-sm">{data.number ?? "DRAFT"}</p>
              <p className="text-xs text-slate-500">Date: {formatDate(data.business_date)}</p>
              {data.due_date ? (
                <p className="text-xs text-slate-500">Due: {formatDate(data.due_date)}</p>
              ) : null}
              <div className="mt-1 flex justify-end gap-1">
                <Badge
                  tone={
                    data.payment_status === "PAID"
                      ? "green"
                      : data.payment_status === "PARTIALLY_PAID"
                        ? "amber"
                        : "slate"
                  }
                >
                  {data.payment_status}
                </Badge>
                {data.lifecycle !== "CONFIRMED" ? (
                  <Badge tone="rose">{data.lifecycle}</Badge>
                ) : null}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 py-4">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Billed to</p>
              <p className="font-medium text-slate-800">{data.customer_name}</p>
              <p className="text-xs text-slate-500">
                {data.customer_code}
                {data.customer_phone ? ` · ${data.customer_phone}` : ""}
              </p>
              {data.customer_address ? (
                <p className="text-xs text-slate-500">{data.customer_address}</p>
              ) : null}
            </div>
            <div className="text-right text-xs text-slate-500">
              <p>
                {data.confirmed_by_name ? `Prepared by: ${data.confirmed_by_name} · ` : ""}
                {data.confirmed_at ? formatDateTime(data.confirmed_at) : "—"}
              </p>
              <p>{data.notes ? `Notes: ${data.notes}` : ""}</p>
              <p>
                {data.prescription_number
                  ? `Rx: ${data.prescription_number}`
                  : ""}
                {data.rx_override ? "Rx override applied. " : ""}
              </p>
            </div>
          </div>

          <table className="w-full border-t border-slate-200 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-2">#</th>
                <th className="py-2">Medicine</th>
                <th className="py-2">Batch</th>
                <th className="py-2 text-right">Qty</th>
                <th className="py-2 text-right">Rate</th>
                <th className="py-2 text-right">Discount</th>
                <th className="py-2 text-right">VAT</th>
                <th className="py-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((item) => (
                <tr key={item.id}>
                  <td className="py-2 text-slate-500">{item.line_no}</td>
                  <td className="py-2">
                    {item.medicine_name}
                    {item.is_free_goods ? (
                      <span className="ml-1 text-xs text-primary-700">(free)</span>
                    ) : null}
                    <span className="block font-mono text-xs text-slate-500">
                      {item.medicine_code}
                    </span>
                  </td>
                  <td className="py-2 font-mono text-xs">{item.batch_number}</td>
                  <td className="py-2 text-right">{formatQty(item.qty)}</td>
                  <td className="py-2 text-right">{formatMoney(item.unit_price)}</td>
                  <td className="py-2 text-right">{formatMoney(item.line_discount)}</td>
                  <td className="py-2 text-right">{formatMoney(item.vat_amount)}</td>
                  <td className="py-2 text-right font-medium">{formatMoney(item.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-4 flex justify-end">
            <dl className="w-full max-w-xs space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Subtotal</dt>
                <dd>{formatMoney(data.subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Discount</dt>
                <dd>{formatMoney(data.discount_total)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">VAT</dt>
                <dd>{formatMoney(data.vat_total)}</dd>
              </div>
              {Number(data.round_off) !== 0 ? (
                <div className="flex justify-between">
                  <dt className="text-slate-500">Round off</dt>
                  <dd>{formatMoney(data.round_off)}</dd>
                </div>
              ) : null}
              <div className="flex justify-between border-t border-slate-200 pt-1 text-base font-semibold">
                <dt>Grand total</dt>
                <dd>{formatMoney(data.grand_total)}</dd>
              </div>
              <div className="flex justify-between text-xs">
                <dt className="text-slate-500">Paid</dt>
                <dd>{formatMoney(data.paid_total)}</dd>
              </div>
              <div className="flex justify-between text-xs">
                <dt className="text-slate-500">Outstanding</dt>
                <dd>{formatMoney(data.outstanding)}</dd>
              </div>
            </dl>
          </div>

          <div className="mt-8 grid grid-cols-2 gap-8 border-t border-slate-200 pt-6 text-xs text-slate-500">
            <div>
              <div className="border-t border-slate-400 pt-1">Customer signature</div>
            </div>
            <div>
              <div className="border-t border-slate-400 pt-1 text-right">Authorised signature</div>
            </div>
          </div>

          <p className="mt-4 text-center text-xs text-slate-500">
            This is a computer-generated invoice.{" "}
            {data.credit_override ? "Credit limit override applied. " : ""}
          </p>
        </div>
      ) : null}
    </div>
  );
}
