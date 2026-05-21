import { Badge } from "./ui/badge";
import {
  CLASSIFICATION_LABELS,
  DR_STATUS_LABELS,
  PHASE_STATUS_LABELS,
  PRIORITY_LABELS,
  RESPONSE_STATUS_LABELS,
} from "@/lib/format";
import type {
  Classification,
  DRStatus,
  PhaseStatus,
  Priority,
  ResponseStatus,
} from "@/lib/types";

export function DrStatusBadge({ status }: { status: DRStatus }) {
  const map: Record<DRStatus, Parameters<typeof Badge>[0]["variant"]> = {
    new: "slate",
    assigned: "info",
    drafting: "violet",
    in_review: "warning",
    approved: "success",
    filed: "brand",
    objected: "danger",
  };
  return <Badge variant={map[status]}>{DR_STATUS_LABELS[status]}</Badge>;
}

export function PhaseStatusBadge({ status }: { status: PhaseStatus }) {
  const map: Record<PhaseStatus, Parameters<typeof Badge>[0]["variant"]> = {
    not_started: "slate",
    in_progress: "info",
    filed: "brand",
    closed: "success",
  };
  return <Badge variant={map[status]}>{PHASE_STATUS_LABELS[status]}</Badge>;
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const map: Record<Priority, Parameters<typeof Badge>[0]["variant"]> = {
    low: "slate",
    normal: "default",
    high: "warning",
    urgent: "danger",
  };
  return <Badge variant={map[priority]}>{PRIORITY_LABELS[priority]}</Badge>;
}

export function ClassificationBadge({ value }: { value: Classification }) {
  const map: Record<Classification, Parameters<typeof Badge>[0]["variant"]> = {
    public: "slate",
    confidential: "warning",
    privileged: "danger",
  };
  return (
    <Badge variant={map[value]}>{CLASSIFICATION_LABELS[value]}</Badge>
  );
}

export function ResponseStatusBadge({ status }: { status: ResponseStatus }) {
  const map: Record<ResponseStatus, Parameters<typeof Badge>[0]["variant"]> = {
    draft: "slate",
    in_review: "warning",
    approved: "success",
    filed: "brand",
    withdrawn: "danger",
  };
  return <Badge variant={map[status]}>{RESPONSE_STATUS_LABELS[status]}</Badge>;
}
