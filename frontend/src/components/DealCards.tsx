import { useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import type { DealResponse } from "../api/types";
import { formatCurrency, formatDate, formatDateTime } from "../lib/format";
import { DEAL_STATUS_VARIANT, PAYMENT_STATUS_VARIANT } from "./DealsTable";
import { Badge, Button, Panel } from "./ui";

/** A compact, tap-to-expand list of deals for narrow screens - the
 * data-table alternative doesn't fit a phone width without horizontal
 * scrolling, which buries columns rather than showing them.
 *
 * Collapsed, the whole card is the expand trigger. Expanded, only the
 * explicit close button collapses it back - tapping a link or action
 * button inside shouldn't also toggle the card shut underneath it. */
export function DealCards({
  items,
  onDownloadIcs,
  onDelete,
}: {
  items: DealResponse[];
  onDownloadIcs: (deal: DealResponse) => void;
  onDelete: (deal: DealResponse) => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  return (
    <div className="stack deal-cards">
      {items.map((deal) => {
        const isOpen = expandedId === deal.id;

        return (
          <Panel
            key={deal.id}
            as="article"
            className="deal-card"
            {...(isOpen
              ? {}
              : {
                  role: "button",
                  tabIndex: 0,
                  onClick: () => setExpandedId(deal.id),
                  onKeyDown: (event: KeyboardEvent) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setExpandedId(deal.id);
                    }
                  },
                })}
          >
            <div className="deal-card__head">
              <div className="deal-card__heading">
                <div className="deal-card__title">{deal.title}</div>
                <div className="deal-card__brand">{deal.brand_name}</div>
              </div>
              {isOpen && (
                <Button
                  variant="quiet"
                  icon
                  small
                  aria-label="Collapse"
                  onClick={() => setExpandedId(null)}
                >
                  ✕
                </Button>
              )}
            </div>

            <div className="deal-card__badges">
              <Badge variant={DEAL_STATUS_VARIANT[deal.deal_status]}>{deal.deal_status}</Badge>
              <Badge variant={PAYMENT_STATUS_VARIANT[deal.payment_status]}>{deal.payment_status}</Badge>
            </div>

            {!isOpen ? (
              <div className="deal-card__meta">
                <span>{formatDate(deal.shoot_at)}</span>
                <span className="deal-card__amount">
                  {formatCurrency(deal.payment_amount, deal.currency)}
                </span>
              </div>
            ) : (
              <>
                <dl className="deal-card__details">
                  <div className="detail-row">
                    <dt>Shoot</dt>
                    <dd>{formatDateTime(deal.shoot_at)}</dd>
                  </div>
                  <div className="detail-row">
                    <dt>Amount</dt>
                    <dd>{formatCurrency(deal.payment_amount, deal.currency)}</dd>
                  </div>
                  <div className="detail-row">
                    <dt>Payment due</dt>
                    <dd>{formatDate(deal.payment_due_date)}</dd>
                  </div>
                  {deal.deliverables && (
                    <div className="detail-row">
                      <dt>Deliverables</dt>
                      <dd>{deal.deliverables}</dd>
                    </div>
                  )}
                  {deal.description && (
                    <div className="detail-row">
                      <dt>Description</dt>
                      <dd>{deal.description}</dd>
                    </div>
                  )}
                  {deal.notes && (
                    <div className="detail-row">
                      <dt>Notes</dt>
                      <dd>{deal.notes}</dd>
                    </div>
                  )}
                  {deal.work_link && (
                    <div className="detail-row">
                      <dt>Link</dt>
                      <dd>
                        <a href={deal.work_link} target="_blank" rel="noreferrer noopener">
                          {deal.work_link}
                        </a>
                      </dd>
                    </div>
                  )}
                </dl>

                <div className="row row-wrap deal-card__actions">
                  <Link to={`/deals/${deal.id}/edit`}>
                    <Button variant="quiet" small>
                      Edit
                    </Button>
                  </Link>
                  <Button variant="quiet" small onClick={() => onDownloadIcs(deal)}>
                    Download .ics
                  </Button>
                  <Button
                    variant="danger"
                    small
                    onClick={() => {
                      if (window.confirm(`Delete "${deal.title}"? This cannot be undone.`)) {
                        onDelete(deal);
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </>
            )}
          </Panel>
        );
      })}
    </div>
  );
}
