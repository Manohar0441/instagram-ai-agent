import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { deleteDeal, downloadDealIcs, getEarningsSummary, listDeals } from "../../api/deals";
import { ApiError } from "../../api/client";
import type { DealResponse, DealStatus, EarningsPeriod, PaymentStatus } from "../../api/types";
import { DealsTable } from "../../components/DealsTable";
import { PageHeader } from "../../components/layout/PageHeader";
import { ApiErrorState, QueryState } from "../../components/QueryState";
import {
  Button,
  Callout,
  EmptyState,
  Field,
  Panel,
  Select,
  SegmentedControl,
  SkeletonCards,
  StatCard,
} from "../../components/ui";
import { TrendChart } from "../../components/charts/Chart";
import { formatCurrency, formatDate } from "../../lib/format";

const PERIOD_OPTIONS = [
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "yearly", label: "Yearly" },
] as const;

const DEAL_STATUS_OPTIONS = [
  { value: "", label: "Any deal status" },
  { value: "negotiating", label: "Negotiating" },
  { value: "confirmed", label: "Confirmed" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

const PAYMENT_STATUS_OPTIONS = [
  { value: "", label: "Any payment status" },
  { value: "unpaid", label: "Unpaid" },
  { value: "partial", label: "Partial" },
  { value: "paid", label: "Paid" },
];

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.detail
    : "Could not reach the server. Is the API running?";
}

export function DealsPage() {
  const queryClient = useQueryClient();

  const [dealStatus, setDealStatus] = useState<DealStatus | "">("");
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus | "">("");
  const [shootFrom, setShootFrom] = useState("");
  const [shootTo, setShootTo] = useState("");
  const [period, setPeriod] = useState<EarningsPeriod>("monthly");
  const [icsError, setIcsError] = useState<string | null>(null);

  const filters = {
    dealStatus: dealStatus || undefined,
    paymentStatus: paymentStatus || undefined,
    shootFrom: shootFrom || undefined,
    shootTo: shootTo || undefined,
  };

  const deals = useQuery({
    queryKey: ["deals", filters],
    queryFn: () => listDeals(filters),
  });

  const earnings = useQuery({
    queryKey: ["deals-earnings", period],
    queryFn: () => getEarningsSummary(period),
  });

  const removeDeal = useMutation({
    mutationFn: (deal: DealResponse) => deleteDeal(deal.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      queryClient.invalidateQueries({ queryKey: ["deals-earnings"] });
    },
  });

  async function handleDownloadIcs(deal: DealResponse) {
    setIcsError(null);
    try {
      await downloadDealIcs(deal.id);
    } catch (error) {
      setIcsError(errorMessage(error));
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Business"
        title="Deals"
        description="Every brand collaboration, its schedule, and what it pays."
        actions={
          <Link to="/deals/new">
            <Button variant="primary">Add deal</Button>
          </Link>
        }
      />

      <div className="stack-lg">
        <section className="stack">
          <div className="row row-wrap" style={{ justifyContent: "space-between" }}>
            <h2>Earnings</h2>
            <SegmentedControl
              label="Earnings period"
              options={PERIOD_OPTIONS}
              value={period}
              onChange={setPeriod}
            />
          </div>

          {earnings.isLoading ? (
            <SkeletonCards count={2} />
          ) : (
            <QueryState isLoading={false} error={earnings.error} loadingLabel="Loading earnings">
              {earnings.data && earnings.data.currencies.length > 0 ? (
                <div className="stack-lg">
                  {earnings.data.currencies.map((currency) => (
                    <div key={currency.currency} className="stack">
                      <section className="grid">
                        <div className="col-3">
                          <StatCard
                            label={`Paid (${currency.currency})`}
                            icon="◎"
                            value={formatCurrency(currency.total_paid, currency.currency)}
                            note={`${currency.deals_counted} deal${currency.deals_counted === 1 ? "" : "s"}`}
                          />
                        </div>
                        <div className="col-3">
                          <StatCard
                            label={`Pending (${currency.currency})`}
                            icon="◑"
                            value={formatCurrency(currency.total_pending, currency.currency)}
                          />
                        </div>
                      </section>
                      {currency.points.length > 1 && (
                        <TrendChart
                          title={`Paid over time — ${currency.currency}`}
                          seriesName="Paid"
                          points={currency.points.map((point) => ({
                            label: formatDate(point.period_start),
                            value: point.paid_total,
                          }))}
                        />
                      )}
                    </div>
                  ))}
                  {earnings.data.excluded_undated_count > 0 && (
                    <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
                      {earnings.data.excluded_undated_count} deal
                      {earnings.data.excluded_undated_count === 1 ? "" : "s"} without a shoot or
                      due date are counted in the totals above but not shown on the timeline.
                    </p>
                  )}
                </div>
              ) : (
                <EmptyState
                  title="No earnings yet"
                  body="Log a deal with a payment amount to start tracking income."
                />
              )}
            </QueryState>
          )}
        </section>

        <section className="stack">
          <h2>All deals</h2>

          <Panel className="stack">
            <div className="grid">
              <div className="col-3">
                <Select
                  label="Deal status"
                  options={DEAL_STATUS_OPTIONS}
                  value={dealStatus}
                  onChange={(event) => setDealStatus(event.target.value as DealStatus | "")}
                />
              </div>
              <div className="col-3">
                <Select
                  label="Payment status"
                  options={PAYMENT_STATUS_OPTIONS}
                  value={paymentStatus}
                  onChange={(event) => setPaymentStatus(event.target.value as PaymentStatus | "")}
                />
              </div>
              <div className="col-3">
                <Field
                  label="Shoot from"
                  type="date"
                  value={shootFrom}
                  onChange={(event) => setShootFrom(event.target.value)}
                />
              </div>
              <div className="col-3">
                <Field
                  label="Shoot to"
                  type="date"
                  value={shootTo}
                  onChange={(event) => setShootTo(event.target.value)}
                />
              </div>
            </div>
          </Panel>

          {icsError && <Callout tone="error">{icsError}</Callout>}
          {removeDeal.isError && <Callout tone="error">{errorMessage(removeDeal.error)}</Callout>}

          {deals.isLoading ? (
            <SkeletonCards count={4} />
          ) : deals.error ? (
            <ApiErrorState error={deals.error} />
          ) : deals.data && deals.data.length > 0 ? (
            <Panel>
              <DealsTable
                items={deals.data}
                onDownloadIcs={handleDownloadIcs}
                onDelete={(deal) => removeDeal.mutate(deal)}
              />
            </Panel>
          ) : (
            <EmptyState
              title="No deals logged yet"
              body="Add your first collaboration to start tracking it."
              actions={
                <Link to="/deals/new">
                  <Button variant="primary" small>
                    Add deal
                  </Button>
                </Link>
              }
            />
          )}
        </section>
      </div>
    </>
  );
}
