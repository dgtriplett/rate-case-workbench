import { format, formatDistanceToNowStrict, isValid, parseISO } from "date-fns";
import type {
  Classification,
  DRStatus,
  PhaseStatus,
  PhaseType,
  Priority,
  ResponseStatus,
} from "./types";

export function fmtDate(value?: string | null) {
  if (!value) return "—";
  const d = typeof value === "string" ? parseISO(value) : value;
  if (!isValid(d)) return "—";
  return format(d, "MMM d, yyyy");
}

export function fmtDateTime(value?: string | null) {
  if (!value) return "—";
  const d = typeof value === "string" ? parseISO(value) : value;
  if (!isValid(d)) return "—";
  return format(d, "MMM d, yyyy h:mm a");
}

export function fmtRelative(value?: string | null) {
  if (!value) return "—";
  const d = typeof value === "string" ? parseISO(value) : value;
  if (!isValid(d)) return "—";
  return formatDistanceToNowStrict(d, { addSuffix: true });
}

export function daysUntil(value?: string | null): number | null {
  if (!value) return null;
  const d = parseISO(value);
  if (!isValid(d)) return null;
  const ms = d.getTime() - Date.now();
  return Math.round(ms / (1000 * 60 * 60 * 24));
}

export const PHASE_LABELS: Record<PhaseType, string> = {
  pre_filing: "Pre-filing",
  filing: "Filing",
  discovery: "Discovery",
  direct_testimony: "Direct testimony",
  rebuttal: "Rebuttal",
  surrebuttal: "Surrebuttal",
  hearing: "Hearing",
  post_hearing_briefs: "Post-hearing briefs",
  order: "Order",
  compliance: "Compliance",
};

export const PHASE_STATUS_LABELS: Record<PhaseStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  filed: "Filed",
  closed: "Closed",
};

export const DR_STATUS_LABELS: Record<DRStatus, string> = {
  new: "New",
  assigned: "Assigned",
  drafting: "Drafting",
  in_review: "In review",
  approved: "Approved",
  filed: "Filed",
  objected: "Objected",
};

export const RESPONSE_STATUS_LABELS: Record<ResponseStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  approved: "Approved",
  filed: "Filed",
  withdrawn: "Withdrawn",
};

export const PRIORITY_LABELS: Record<Priority, string> = {
  low: "Low",
  normal: "Normal",
  high: "High",
  urgent: "Urgent",
};

export const CLASSIFICATION_LABELS: Record<Classification, string> = {
  public: "Public",
  confidential: "Confidential",
  privileged: "Privileged",
};
