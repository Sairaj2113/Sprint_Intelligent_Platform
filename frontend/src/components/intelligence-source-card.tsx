import type { GroundedAnalysisSource } from "../types/api";

type IntelligenceSourceCardProps = {
  source: GroundedAnalysisSource;
};

const sourceTypeLabels: Record<GroundedAnalysisSource["source_type"], string> = {
  ISSUE: "Issue",
  TEST: "Test Result",
  DEPLOYMENT: "Deployment",
  COMMENT: "Comment",
  DOCUMENT: "Document",
};

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").toLowerCase();
}

function SourceField({ label, value, secondary = false }: { label: string; value: string | number; secondary?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className={`mt-1 break-words text-sm ${secondary ? "font-mono text-xs text-slate-600" : "font-medium text-slate-800"}`}>
        {value}
      </dd>
    </div>
  );
}

export function IntelligenceSourceCard({ source }: IntelligenceSourceCardProps) {
  return (
    <section
      className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:p-5"
      aria-labelledby="selected-evidence-heading"
    >
      <h4 id="selected-evidence-heading" className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
        Selected evidence
      </h4>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="rounded border border-slate-200 bg-white px-2 py-1 font-mono text-xs font-semibold text-slate-700">
          {source.source_id}
        </span>
        <span className="text-sm font-medium text-slate-600">{sourceTypeLabels[source.source_type]}</span>
      </div>
      <p className="mt-4 break-words text-base font-semibold text-slate-950">
        {source.title}
      </p>

      <dl className="mt-5 grid gap-x-5 gap-y-4 sm:grid-cols-2">
        {source.issue_key ? <SourceField label="Issue" value={source.issue_key} /> : null}
        {source.document_type ? <SourceField label="Document type" value={formatLabel(source.document_type)} /> : null}
        {source.section_title ? <SourceField label="Section" value={source.section_title} /> : null}
        {source.page_number !== null ? <SourceField label="Page" value={source.page_number} /> : null}
        {source.record_id ? <SourceField label="Record ID" value={source.record_id} secondary /> : null}
      </dl>
    </section>
  );
}
