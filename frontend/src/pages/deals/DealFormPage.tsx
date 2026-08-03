import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { createDeal, getDeal, updateDeal } from "../../api/deals";
import type { DealStatus, DealWriteRequest, PaymentStatus } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Callout, Field, LoadingPage, Select, Textarea } from "../../components/ui";

const DEAL_STATUS_OPTIONS = [
  { value: "negotiating", label: "Negotiating" },
  { value: "confirmed", label: "Confirmed" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

const PAYMENT_STATUS_OPTIONS = [
  { value: "unpaid", label: "Unpaid" },
  { value: "partial", label: "Partial" },
  { value: "paid", label: "Paid" },
];

interface FormState {
  title: string;
  brandName: string;
  description: string;
  deliverables: string;
  dealStatus: DealStatus;
  shootAt: string;
  paymentAmount: string;
  currency: string;
  paymentStatus: PaymentStatus;
  paymentDueDate: string;
  workLink: string;
  notes: string;
}

const EMPTY_FORM: FormState = {
  title: "",
  brandName: "",
  description: "",
  deliverables: "",
  dealStatus: "negotiating",
  shootAt: "",
  paymentAmount: "",
  currency: "INR",
  paymentStatus: "unpaid",
  paymentDueDate: "",
  workLink: "",
  notes: "",
};

/** Converts a stored UTC ISO datetime into the value a <input type="datetime-local"> needs. */
function toDatetimeLocalValue(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromDatetimeLocalValue(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function toPayload(form: FormState): DealWriteRequest {
  return {
    title: form.title.trim(),
    brand_name: form.brandName.trim(),
    description: form.description.trim() || null,
    deliverables: form.deliverables.trim() || null,
    deal_status: form.dealStatus,
    shoot_at: fromDatetimeLocalValue(form.shootAt),
    payment_amount: form.paymentAmount.trim() === "" ? null : Number(form.paymentAmount),
    currency: form.currency.trim().toUpperCase() || "INR",
    payment_status: form.paymentStatus,
    payment_due_date: form.paymentDueDate.trim() || null,
    work_link: form.workLink.trim() || null,
    notes: form.notes.trim() || null,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.detail
    : "Could not reach the server. Is the API running?";
}

export function DealFormPage() {
  const { id } = useParams();
  const dealId = id ? Number(id) : undefined;
  const isEditing = dealId !== undefined;

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const existing = useQuery({
    queryKey: ["deal", dealId],
    queryFn: () => getDeal(dealId as number),
    enabled: isEditing,
  });

  useEffect(() => {
    if (!existing.data) return;
    const deal = existing.data;
    setForm({
      title: deal.title,
      brandName: deal.brand_name,
      description: deal.description ?? "",
      deliverables: deal.deliverables ?? "",
      dealStatus: deal.deal_status,
      shootAt: toDatetimeLocalValue(deal.shoot_at),
      paymentAmount: deal.payment_amount === null ? "" : String(deal.payment_amount),
      currency: deal.currency,
      paymentStatus: deal.payment_status,
      paymentDueDate: deal.payment_due_date ?? "",
      workLink: deal.work_link ?? "",
      notes: deal.notes ?? "",
    });
  }, [existing.data]);

  const save = useMutation({
    mutationFn: (payload: DealWriteRequest) =>
      isEditing ? updateDeal(dealId as number, payload) : createDeal(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["deals"] });
      await queryClient.invalidateQueries({ queryKey: ["deals-earnings"] });
      navigate("/deals");
    },
  });

  if (isEditing && existing.isLoading) {
    return <LoadingPage label="Loading deal" />;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate(toPayload(form));
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  return (
    <>
      <PageHeader
        eyebrow="Deals"
        title={isEditing ? "Edit deal" : "Add deal"}
        description="Log what the work is, when it happens, and what it pays — only Title and Brand are required."
      />

      <form className="stack-lg" style={{ maxWidth: "48rem" }} onSubmit={handleSubmit}>
        {save.isError && <Callout tone="error">{errorMessage(save.error)}</Callout>}

        <section className="stack">
          <h2>The work</h2>
          <div className="grid">
            <div className="col-6">
              <Field
                label="Title"
                required
                placeholder="Instagram Reel Campaign"
                value={form.title}
                onChange={(event) => update("title", event.target.value)}
              />
            </div>
            <div className="col-6">
              <Field
                label="Brand / company"
                required
                placeholder="Acme Skincare"
                value={form.brandName}
                onChange={(event) => update("brandName", event.target.value)}
              />
            </div>
          </div>
          <Textarea
            label="Description"
            hint="What is this deal?"
            value={form.description}
            onChange={(event) => update("description", event.target.value)}
          />
          <Textarea
            label="Deliverables"
            hint="e.g. 3 reels, 1 static post"
            value={form.deliverables}
            onChange={(event) => update("deliverables", event.target.value)}
          />
          <div className="grid">
            <div className="col-6">
              <Select
                label="Deal status"
                options={DEAL_STATUS_OPTIONS}
                value={form.dealStatus}
                onChange={(event) => update("dealStatus", event.target.value as DealStatus)}
              />
            </div>
            <div className="col-6">
              <Field
                label="Work link"
                type="url"
                placeholder="https://…"
                hint="Contract, brief, or published content"
                value={form.workLink}
                onChange={(event) => update("workLink", event.target.value)}
              />
            </div>
          </div>
        </section>

        <section className="stack rule" style={{ paddingTop: "var(--space-8)" }}>
          <h2>Schedule</h2>
          <div className="grid">
            <div className="col-6">
              <Field
                label="Shoot date & time"
                type="datetime-local"
                value={form.shootAt}
                onChange={(event) => update("shootAt", event.target.value)}
              />
            </div>
          </div>
        </section>

        <section className="stack rule" style={{ paddingTop: "var(--space-8)" }}>
          <h2>Payment</h2>
          <div className="grid">
            <div className="col-4">
              <Field
                label="Amount"
                type="number"
                min="0"
                step="0.01"
                value={form.paymentAmount}
                onChange={(event) => update("paymentAmount", event.target.value)}
              />
            </div>
            <div className="col-4">
              <Field
                label="Currency"
                maxLength={3}
                value={form.currency}
                onChange={(event) => update("currency", event.target.value)}
              />
            </div>
            <div className="col-4">
              <Select
                label="Payment status"
                options={PAYMENT_STATUS_OPTIONS}
                value={form.paymentStatus}
                onChange={(event) => update("paymentStatus", event.target.value as PaymentStatus)}
              />
            </div>
          </div>
          <div className="grid">
            <div className="col-6">
              <Field
                label="Payment due date"
                type="date"
                hint="When you expect to be paid"
                value={form.paymentDueDate}
                onChange={(event) => update("paymentDueDate", event.target.value)}
              />
            </div>
          </div>
        </section>

        <section className="stack rule" style={{ paddingTop: "var(--space-8)" }}>
          <h2>Notes</h2>
          <Textarea
            label="Notes"
            value={form.notes}
            onChange={(event) => update("notes", event.target.value)}
          />
        </section>

        <div className="row row-wrap">
          <Button type="submit" variant="primary" loading={save.isPending}>
            {isEditing ? "Save changes" : "Add deal"}
          </Button>
          <Button type="button" variant="quiet" onClick={() => navigate("/deals")}>
            Cancel
          </Button>
        </div>
      </form>
    </>
  );
}
