import { apiFetch, apiFetchFile } from "./client";
import type {
  DealResponse,
  DealStatus,
  DealWriteRequest,
  EarningsPeriod,
  EarningsSummaryResponse,
  PaymentStatus,
} from "./types";

export interface DealFilters {
  dealStatus?: DealStatus;
  paymentStatus?: PaymentStatus;
  shootFrom?: string;
  shootTo?: string;
}

export async function listDeals(filters: DealFilters = {}): Promise<DealResponse[]> {
  const params = new URLSearchParams();
  if (filters.dealStatus) params.set("deal_status", filters.dealStatus);
  if (filters.paymentStatus) params.set("payment_status", filters.paymentStatus);
  if (filters.shootFrom) params.set("shoot_from", filters.shootFrom);
  if (filters.shootTo) params.set("shoot_to", filters.shootTo);
  const query = params.toString();
  return apiFetch<DealResponse[]>(`/deals${query ? `?${query}` : ""}`);
}

export async function getDeal(id: number): Promise<DealResponse> {
  return apiFetch<DealResponse>(`/deals/${id}`);
}

export async function createDeal(payload: DealWriteRequest): Promise<DealResponse> {
  return apiFetch<DealResponse>("/deals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateDeal(id: number, payload: DealWriteRequest): Promise<DealResponse> {
  return apiFetch<DealResponse>(`/deals/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteDeal(id: number): Promise<void> {
  await apiFetch<void>(`/deals/${id}`, { method: "DELETE" });
}

export async function getEarningsSummary(
  period: EarningsPeriod = "monthly",
): Promise<EarningsSummaryResponse> {
  return apiFetch<EarningsSummaryResponse>(`/deals/earnings-summary?period=${period}`);
}

/** Downloads a deal's .ics calendar file straight into the browser's downloads. */
export async function downloadDealIcs(id: number): Promise<void> {
  const { blob, filename } = await apiFetchFile(`/deals/${id}/ics`, `deal-${id}.ics`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
