"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge, Button, ErrorBanner, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { Purchase } from "@/lib/types";

export default function PurchaseDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["purchase", params.id],
    queryFn: () => api.get<Purchase>(`/purchases/${params.id}/`),
  });

  if (isLoading) return <Spinner label="Loading purchase…" />;

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap items-center justify-between gap-2">
        <Link href="/purchases">
          <Button size="sm" variant="secondary">
            ← Back to purchases
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
            </div>
            <div className="text-right">
              <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">Purchase Record</h2>
              <p className="font-mono text-sm">{data.number ?? "DRAFT"}</p>
              <p className="text-xs text-slate-500">Business date: {data.business_date}</p>
              <p className="text-xs text-slate-500">
                Supplier invoice: {data.supplier_invoice_number || "—"} ({data.supplier_invoice_date || "—"})
              </p>
              <div className="no-print mt-1 flex justify-end gap-1">
                <Badge tone={data.payment_status === "PAID" ? "green" : data.payment_status === "PARTIALLY_PAID" ? "amber" : "slate"}>
                  {data.payment_status}
                </Badge>
                {data.lifecycle !== "CONFIRMED" ? <Badge tone="rose">{data.lifecycle}</Badge> : null}
                {data.return_status !== "NONE" ? <Badge tone="blue">{data.return_status}</Badge> : null}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 py-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Supplier</p>
              <p className="text-sm font-medium">{data.supplier_name}</p>
            </div>
            <div className="text-right">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Amounts (BDT)</p>
              <p className="text-sm">Subtotal {Number(data.subtotal).toFixed(2)}</p>
              <p className="text-sm">Discount −{Number(data.discount_total).toFixed(2)}</p>
              <p className="text-sm">Freight +{Number(data.freight_total).toFixed(2)}</p>
              <p className="text-sm">VAT {Number(data.vat_total).toFixed(2)}</p>
              <p className="text-base font-bold">Grand total {Number(data.grand_total).toFixed(2)}</p>
              <p className="text-sm text-slate-500">Paid {Number(data.paid_total).toFixed(2)} · Outstanding {Number(data.outstanding).toFixed(2)}</p>
            </div>
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="py-2">#</th>
                <th className="py-2">Medicine</th>
                <th className="py-2">Batch</th>
                <th className="py-2 text-right">Expiry</th>
                <th className="py-2 text-right">Qty</th>
                <th className="py-2 text-right">Bonus</th>
                <th className="py-2 text-right">Unit cost</th>
                <th className="py-2 text-right">Discount</th>
                <th className="py-2 text-right">VAT</th>
                <th className="py-2 text-right">Line net</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item, index) => (
                <tr key={item.id} className="border-b border-slate-100">
                  <td className="py-2">{index + 1}</td>
                  <td className="py-2">
                    {item.medicine_name}
                    <span className="block text-xs text-slate-400">{item.medicine_code}</span>
                  </td>
                  <td className="py-2 font-mono text-xs">{item.batch_number}</td>
                  <td className="py-2 text-right">{item.expiry_date ?? "—"}</td>
                  <td className="py-2 text-right">{item.qty_base}</td>
                  <td className="py-2 text-right">{item.bonus_qty_base || 0}</td>
                  <td className="py-2 text-right">{Number(item.unit_cost).toFixed(2)}</td>
                  <td className="py-2 text-right">{Number(item.line_discount).toFixed(2)}</td>
                  <td className="py-2 text-right">{Number(item.vat_amount).toFixed(2)}</td>
                  <td className="py-2 text-right font-medium">{Number(item.line_net).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {data.notes ? (
            <p className="mt-4 text-xs text-slate-500">
              <span className="font-semibold">Notes:</span> {data.notes}
            </p>
          ) : null}
          {data.cancel_reason ? (
            <p className="mt-2 text-xs text-rose-600">
              <span className="font-semibold">Cancelled:</span> {data.cancel_reason}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}