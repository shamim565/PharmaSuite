"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { useAuth } from "@/app/providers";
import { AttachmentPanel } from "@/components/attachments";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Spinner, pushToast } from "@/components/ui";
import { ApiError, api, apiDownload } from "@/lib/api";
import { formatDate, formatDateTime, formatMoney, formatQty } from "@/lib/format";
import type { Paginated, Purchase, SupplierPayment } from "@/lib/types";

function PaymentHistory({ purchaseId }: { purchaseId: string }) {
  const { hasPerm } = useAuth();
  const canView = hasPerm("PURCHASE_PAY");
  const { data, isLoading, error } = useQuery({
    queryKey: ["supplier-payments", "purchase", purchaseId],
    queryFn: () =>
      api.get<Paginated<SupplierPayment>>(`/supplier-payments/?purchase=${purchaseId}&page_size=50`),
    enabled: canView,
  });

  if (!canView) return null;

  return (
    <Card>
      <CardHeader title="Payments" subtitle={data ? `${data.count} payment(s) allocated` : undefined} />
      <ErrorBanner error={error} />
      {isLoading ? (
        <Spinner />
      ) : !data || data.results.length === 0 ? (
        <EmptyState message="No payments recorded for this purchase." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {data.results.map((payment) => (
            <li key={payment.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
              <div>
                <p className="font-medium">{payment.number}</p>
                <p className="text-xs text-slate-500">
                  {formatDate(payment.business_date)} · {payment.method} · {payment.account_name}
                  {payment.reference ? ` · ref ${payment.reference}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-semibold">{formatMoney(payment.amount)}</span>
                {payment.status === "ACTIVE" ? (
                  <Badge tone="green">Active</Badge>
                ) : (
                  <Badge tone="rose">Reversed</Badge>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

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
            <ArrowLeft aria-hidden size={14} />
            Back to purchases
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
                await apiDownload(
                  `/purchases/${data.id}/print/`,
                  `${data.number ?? "purchase"}.pdf`,
                );
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
        <div className="print-container rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
            <div>
              <h1 className="text-xl font-bold text-slate-900">PharmaSuite</h1>
              <p className="text-sm text-slate-600">{data.branch_name}</p>
            </div>
            <div className="text-right">
              <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-700">Purchase Record</h2>
              <p className="font-mono text-sm">{data.number ?? "DRAFT"}</p>
              <p className="text-xs text-slate-500">Business date: {formatDate(data.business_date)}</p>
              <p className="text-xs text-slate-500">
                Supplier invoice: {data.supplier_invoice_number || "—"} (
                {data.supplier_invoice_date ? formatDate(data.supplier_invoice_date) : "—"})
              </p>
              <div className="mt-1 flex justify-end gap-1">
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
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Supplier</p>
              <p className="text-sm font-medium">{data.supplier_name}</p>
              {data.confirmed_at ? (
                <p className="mt-1 text-xs text-slate-500">
                  Confirmed{data.confirmed_by_name ? ` by ${data.confirmed_by_name}` : ""} ·{" "}
                  {formatDateTime(data.confirmed_at)}
                </p>
              ) : null}
            </div>
            <div className="text-right">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Amounts (BDT)</p>
              <p className="text-sm">Subtotal {formatMoney(data.subtotal)}</p>
              <p className="text-sm">Discount −{formatMoney(data.discount_total)}</p>
              <p className="text-sm">Freight +{formatMoney(data.freight_total)}</p>
              <p className="text-sm">VAT {formatMoney(data.vat_total)}</p>
              <p className="text-base font-bold">Grand total {formatMoney(data.grand_total)}</p>
              <p className="text-sm text-slate-500">
                Paid {formatMoney(data.paid_total)} · Outstanding {formatMoney(data.outstanding)}
              </p>
            </div>
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
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
                    <span className="block text-xs text-slate-500">{item.medicine_code}</span>
                  </td>
                  <td className="py-2 font-mono text-xs">{item.batch_number}</td>
                  <td className="py-2 text-right">{item.expiry_date ? formatDate(item.expiry_date) : "—"}</td>
                  <td className="py-2 text-right">{formatQty(item.qty_base)}</td>
                  <td className="py-2 text-right">{formatQty(item.bonus_qty_base || "0")}</td>
                  <td className="py-2 text-right">{formatMoney(item.unit_cost)}</td>
                  <td className="py-2 text-right">{formatMoney(item.line_discount)}</td>
                  <td className="py-2 text-right">{formatMoney(item.vat_amount)}</td>
                  <td className="py-2 text-right font-medium">{formatMoney(item.line_net)}</td>
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
            <p className="mt-2 text-xs text-danger-600">
              <span className="font-semibold">Cancelled:</span> {data.cancel_reason}
            </p>
          ) : null}
        </div>
      ) : null}

      {data ? (
        <>
          <div className="no-print">
            <PaymentHistory purchaseId={data.id} />
          </div>
          <Card className="no-print">
            <div className="p-4">
              <AttachmentPanel
                ownerType="PURCHASE"
                ownerId={data.id}
                title="Supplier invoice & documents"
              />
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}