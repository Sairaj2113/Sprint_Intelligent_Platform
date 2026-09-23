import {
  CircleAlert,
  CircleCheck,
  Info,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import type {
  CitationValidation,
  EvidenceSufficiency,
  EvidenceSufficiencyStatus,
} from "../types/api";

type EvidenceStatusPanelProps = {
  evidence: EvidenceSufficiency;
  sourceCount: number;
  citationValidation?: CitationValidation | null;
};

type StatusPresentation = {
  label: string;
  description: string;
  icon: LucideIcon;
  panelClassName: string;
  iconClassName: string;
};

const statusPresentations: Record<EvidenceSufficiencyStatus, StatusPresentation> = {
  SUFFICIENT: {
    label: "Sufficient evidence",
    description: "The available evidence supports this analysis.",
    icon: CircleCheck,
    panelClassName: "border-emerald-200 bg-emerald-50",
    iconClassName: "text-emerald-700",
  },
  LIMITED: {
    label: "Limited evidence",
    description: "This analysis can be provided, but the available evidence has limitations.",
    icon: TriangleAlert,
    panelClassName: "border-amber-200 bg-amber-50",
    iconClassName: "text-amber-700",
  },
  INSUFFICIENT: {
    label: "Insufficient evidence",
    description: "There is not enough available evidence to produce a grounded answer for this question.",
    icon: Info,
    panelClassName: "border-sky-200 bg-sky-50",
    iconClassName: "text-sky-700",
  },
  INVALID_CITATIONS: {
    label: "Citation validation issue",
    description: "The generated analysis contains one or more citations that could not be validated against the available evidence sources.",
    icon: CircleAlert,
    panelClassName: "border-rose-200 bg-rose-50",
    iconClassName: "text-rose-700",
  },
};

function uniqueText(values: string[]): string[] {
  return Array.from(new Set(values));
}

export function EvidenceStatusPanel({
  evidence,
  sourceCount,
  citationValidation = null,
}: EvidenceStatusPanelProps) {
  const presentation = statusPresentations[evidence.status];
  const Icon = presentation.icon;
  const reasons = uniqueText(evidence.reasons);
  const limitations = uniqueText(evidence.limitations);
  const invalidSourceIds = evidence.status === "INVALID_CITATIONS"
    ? uniqueText(citationValidation?.invalid_source_ids ?? [])
    : [];

  return (
    <section
      className={`mt-5 rounded-lg border p-4 sm:p-5 ${presentation.panelClassName}`}
      aria-labelledby="evidence-status-heading"
    >
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 size-5 shrink-0 ${presentation.iconClassName}`} aria-hidden="true" />
        <div>
          <h3 id="evidence-status-heading" className="text-base font-semibold text-slate-950">
            {presentation.label}
          </h3>
          <p className="mt-1 text-sm leading-6 text-slate-700">{presentation.description}</p>
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-600">
        {sourceCount} evidence {sourceCount === 1 ? "source" : "sources"} available
      </p>

      {reasons.length > 0 ? (
        <section className="mt-4 border-t border-slate-200/80 pt-4" aria-labelledby="evidence-reasons-heading">
          <h4 id="evidence-reasons-heading" className="text-sm font-semibold text-slate-800">
            Why this status?
          </h4>
          <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-700">
            {reasons.map((reason) => <li key={reason} className="break-words">{reason}</li>)}
          </ul>
        </section>
      ) : null}

      {limitations.length > 0 ? (
        <section className="mt-4 border-t border-slate-200/80 pt-4" aria-labelledby="evidence-limitations-heading">
          <h4 id="evidence-limitations-heading" className="text-sm font-semibold text-slate-800">
            Evidence limitations
          </h4>
          <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-700">
            {limitations.map((limitation) => <li key={limitation} className="break-words">{limitation}</li>)}
          </ul>
        </section>
      ) : null}

      {invalidSourceIds.length > 0 ? (
        <section className="mt-4 border-t border-slate-200/80 pt-4" aria-labelledby="invalid-source-references-heading">
          <h4 id="invalid-source-references-heading" className="text-sm font-semibold text-slate-800">
            Invalid source references
          </h4>
          <div className="mt-2 flex flex-wrap gap-2">
            {invalidSourceIds.map((sourceId) => (
              <span
                key={sourceId}
                className="inline-flex items-center whitespace-nowrap rounded-md border border-rose-200 bg-white/70 px-2.5 py-1 font-mono text-xs font-medium text-rose-800"
              >
                {sourceId}
              </span>
            ))}
          </div>
        </section>
      ) : null}
    </section>
  );
}
