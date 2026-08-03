import { Link } from "react-router-dom";

import type { DealResponse } from "../api/types";
import { formatCurrency, formatDate, formatDateTime } from "../lib/format";
import { Badge, Button } from "./ui";

export const DEAL_STATUS_VARIANT: Record<DealResponse["deal_status"], "default" | "accent" | "solid"> = {
  negotiating: "default",
  confirmed: "accent",
  completed: "solid",
  cancelled: "default",
};

export const PAYMENT_STATUS_VARIANT: Record<DealResponse["payment_status"], "default" | "accent" | "solid"> = {
  unpaid: "default",
  partial: "accent",
  paid: "solid",
};

export function DealsTable({
  items,
  onDownloadIcs,
  onDelete,
}: {
  items: DealResponse[];
  onDownloadIcs: (deal: DealResponse) => void;
  onDelete: (deal: DealResponse) => void;
}) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Title</th>
            <th scope="col">Brand</th>
            <th scope="col">Deal status</th>
            <th scope="col">Shoot</th>
            <th scope="col" className="numeric">
              Amount
            </th>
            <th scope="col">Payment status</th>
            <th scope="col">Due</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((deal) => (
            <tr key={deal.id}>
              <td>
                {deal.work_link ? (
                  <a href={deal.work_link} target="_blank" rel="noreferrer noopener">
                    {deal.title}
                  </a>
                ) : (
                  deal.title
                )}
              </td>
              <td>{deal.brand_name}</td>
              <td>
                <Badge variant={DEAL_STATUS_VARIANT[deal.deal_status]}>{deal.deal_status}</Badge>
              </td>
              <td>{formatDateTime(deal.shoot_at)}</td>
              <td className="numeric">{formatCurrency(deal.payment_amount, deal.currency)}</td>
              <td>
                <Badge variant={PAYMENT_STATUS_VARIANT[deal.payment_status]}>
                  {deal.payment_status}
                </Badge>
              </td>
              <td>{formatDate(deal.payment_due_date)}</td>
              <td>
                <div className="row row-wrap">
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
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
