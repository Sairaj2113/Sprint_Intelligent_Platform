import type {
  CitationValidation,
  EvidenceSufficiency,
  GroundedAnswer,
  GroundedAnalysisSource,
} from "../types/api";
import { useMemo, useState } from "react";

import { EvidenceStatusPanel } from "./evidence-status-panel";
import { IntelligenceSourceCard } from "./intelligence-source-card";

type GroundedAnswerPanelProps = {
  answer: GroundedAnswer;
  question: string;
  evidence: EvidenceSufficiency;
  sourceCount: number;
  sources: GroundedAnalysisSource[];
  citationValidation?: CitationValidation | null;
};

function answerParagraphs(answer: string): string[] {
  return answer
    .split(/\r?\n\s*\r?\n/)
    .filter((paragraph) => paragraph.trim().length > 0);
}

export function GroundedAnswerPanel({
  answer,
  question,
  evidence,
  sourceCount,
  sources,
  citationValidation,
}: GroundedAnswerPanelProps) {
  const paragraphs = answerParagraphs(answer.answer);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const sourceMap = useMemo(
    () => new Map(sources.map((source) => [source.source_id, source])),
    [sources],
  );
  const selectedSource = selectedSourceId ? sourceMap.get(selectedSourceId) : undefined;

  return (
    <section
      className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
      aria-labelledby="grounded-analysis-heading"
    >
      <header className="border-b border-slate-100 pb-5">
        <h2 id="grounded-analysis-heading" className="text-lg font-semibold text-slate-950">
          Analysis
        </h2>
        <p className="mt-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Question
        </p>
        <p className="mt-1 text-sm leading-6 text-slate-700">{question}</p>
      </header>

      <EvidenceStatusPanel
        evidence={evidence}
        sourceCount={sourceCount}
        citationValidation={citationValidation}
      />

      <div className="mt-5 space-y-4 text-sm leading-6 text-slate-700">
        {paragraphs.map((paragraph, index) => (
          <p key={index} className="whitespace-pre-wrap">
            {paragraph}
          </p>
        ))}
      </div>

      {answer.claims.length > 0 ? (
        <section className="mt-7 border-t border-slate-100 pt-5" aria-labelledby="grounded-claims-heading">
          <h3 id="grounded-claims-heading" className="text-base font-semibold text-slate-900">
            Grounded claims
          </h3>
          <ol className="mt-4 list-decimal space-y-4 pl-5 text-sm leading-6 text-slate-700">
            {answer.claims.map((claim, claimIndex) => (
              <li key={`${claim.statement}-${claimIndex}`} className="pl-1">
                <p>{claim.statement}</p>
                {claim.source_ids.length > 0 ? (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-slate-500">Sources</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {claim.source_ids.map((sourceId, sourceIndex) => {
                        const source = sourceMap.get(sourceId);
                        const isSelected = selectedSourceId === sourceId;

                        return source ? (
                          <button
                            key={`${sourceId}-${sourceIndex}`}
                            type="button"
                            onClick={() => setSelectedSourceId(sourceId)}
                            aria-pressed={isSelected}
                            aria-label={`View evidence source ${sourceId}`}
                            className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-md border px-2.5 py-1 font-mono text-xs font-medium transition focus:outline-none focus:ring-2 focus:ring-sky-300 focus:ring-offset-2 ${
                              isSelected
                                ? "border-sky-600 bg-sky-50 font-semibold text-sky-800 shadow-sm"
                                : "border-slate-200 bg-slate-50 text-slate-700 hover:border-sky-300 hover:bg-sky-50"
                            }`}
                          >
                            {sourceId}
                          </button>
                        ) : (
                          <span
                            key={`${sourceId}-${sourceIndex}`}
                            aria-label={`${sourceId}: source details unavailable`}
                            className="inline-flex shrink-0 items-center whitespace-nowrap rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1 font-mono text-xs font-medium text-slate-500"
                          >
                            {sourceId}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
          {selectedSource ? <IntelligenceSourceCard source={selectedSource} /> : null}
        </section>
      ) : null}

      {answer.limitations.length > 0 ? (
        <section className="mt-7 border-t border-slate-100 pt-5" aria-labelledby="analysis-limitations-heading">
          <h3 id="analysis-limitations-heading" className="text-base font-semibold text-slate-900">
            Limitations
          </h3>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600">
            {answer.limitations.map((limitation, index) => (
              <li key={`${limitation}-${index}`}>{limitation}</li>
            ))}
          </ul>
        </section>
      ) : null}

    </section>
  );
}
