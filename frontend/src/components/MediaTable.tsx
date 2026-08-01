import type { MediaAnalyticsResponse } from "../api/types";
import {
  formatDate,
  formatMediaType,
  formatNumber,
  formatPercent,
  truncate,
} from "../lib/format";

/** The shared post table. Every numeric column preserves null as an em-dash. */
export function MediaTable({ items }: { items: MediaAnalyticsResponse[] }) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Post</th>
            <th scope="col">Type</th>
            <th scope="col">Posted</th>
            <th scope="col" className="numeric">
              Likes
            </th>
            <th scope="col" className="numeric">
              Comments
            </th>
            <th scope="col" className="numeric">
              Reach
            </th>
            <th scope="col" className="numeric">
              Engagement
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.media_id}>
              <td>
                {item.permalink ? (
                  <a href={item.permalink} target="_blank" rel="noreferrer noopener">
                    {truncate(item.caption, 48)}
                  </a>
                ) : (
                  truncate(item.caption, 48)
                )}
              </td>
              <td>{formatMediaType(item.media_type)}</td>
              <td>{formatDate(item.posted_at)}</td>
              <td className="numeric">{formatNumber(item.likes)}</td>
              <td className="numeric">{formatNumber(item.comments)}</td>
              <td className="numeric">{formatNumber(item.reach)}</td>
              <td className="numeric">{formatPercent(item.engagement_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
