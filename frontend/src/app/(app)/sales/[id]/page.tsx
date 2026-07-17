"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge, Button, ErrorBanner, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
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
            ← Back to sales
          </Button>
        </Link>
        <Button size="sm" onClick={() => window.print()} disabled={!data}>
          Print (A4)
        </Button>
      </div>

      <ErrorBanner error={error} />

      {data ? (
        <div className="print-container rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
            <div>
              <h1 className="text-xl font-bold text-slate-900">Medicine Dealer ERP</h1>
              <p className="text-sm text-slate-600">{data.branch_name}</p>
              <p className="text-xs text-slate-500">
                {data.branch_address}
                {data.branch_phone ? ` · ${data.branch_phone}` : ""}
              </p>
            </div>
            <div className="text-right">
              <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">Invoice</h2>
              <p className="font-mono text-sm">{data.number ?? "DRAFT"}</p>
              <p className="text-xs text-slate-500">Date: {data.business_date}</p>
              {data.due_date ? <p className="text-xs text-slate-500">Due: {data.due_date}</p> : null}
              <div className="no-print mt-1 flex justify-end gap-1">
                <Badge tone={data.payment_status === "PAID" ? "green" : data.payment_status === "PARTIALLY_PAID" ? "amber" : "slate"}>
                  {data.payment_status}
                </Badge>
                {data.lifecycle !== "CONFIRMED" ? <Badge tone="rose">{data.lifecycle}</Badge> : null}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 py-4">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">Billed to</p>
              <p className="font-medium text-slate-800">{data.customer_name}</p>
              <p className="text-xs text-slate-500">
                {data.customer_code}
                {data.customer_phone ? ` · ${data.customer_phone}` : ""}
              </p>
              {data.customer_address ? <p className="text-xs text-slate-500">{data.customer_address}</p> : null}
            </div>
            <div className="text-right text-xs text-slate-500">
              <p>Prepared by: {data.confirmed_at ? "Counter" : "—"}</p>
              <p>{data.notes ? `Notes: ${data.notes}` : ""}</p>
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
                    {item.is_free_goods ? <span className="ml-1 text-xs text-emerald-700">(free)</span> : null}
                    <span className="block font-mono text-[10px] text-slate-400">{item.medicine_code}</span>
                  </td>
                  <td className="py-2 font-mono text-xs">{item.batch_number}</td>
                  <td className="py-2 text-right">{item.qty}</td>
                  <td className="py-2 text-right">{item.unit_price}</td>
                  <td className="py-2 text-right">{item.line_discount}</td>
                  <td className="py-2 text-right">{item.vat_amount}</td>
                  <td className="py-2 text-right font-medium">{item.line_total}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-4 flex justify-end">
            <dl className="w-full max-w-xs space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Subtotal</dt>
                <dd>{data.subtotal}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Discount</dt>
                <dd>{data.discount_total}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">VAT</dt>
                <dd>{data.vat_total}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Round off</dt>
                <dd>{data.round_off}</dd>
              </div>
              <div className="flex justify-between border-t border-slate-200 pt-1 text-base font-semibold">
                <dt>Grand total</dt>
                <dd>{data.grand_total}</dd>
              </div>
              <div className="flex justify-between text-xs">
                <dt className="text-slate-500">Paid</dt>
                <dd>{data.paid_total}</dd>
              </div>
              <div className="flex justify-between text-xs">
                <dt className="text-slate-500">Outstanding</dt>
                <dd>{data.outstanding}</dd>
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

          <p className="mt-4 text-center text-[10px] text-slate-400">
            This is a computer-generated invoice. {data.credit_override ? "Credit limit override applied. " : ""}
          </p>
        </div>
      ) : null}
    </div>
  );
}
