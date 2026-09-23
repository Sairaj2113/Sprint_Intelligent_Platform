import type {
  EvidenceSufficiencyStatus,
  GroundedAnswer,
} from "../types/api";

type GroundedAnswerPanelProps = {
  answer: GroundedAnswer;
  question: string;
  evidenceStatus: EvidenceSufficiencyStatus;
  sourceCount: number;
};

function answerParagraphs(answer: string): string[] {
  return answer
    .split(/\r?\n\s*\r?\n/)
    .filter((paragraph) => paragraph.trim().length > 0);
}

export function GroundedAnswerPanel({
  answer,
  question,
  evidenceStatus,
  sourceCount,
}: GroundedAnswerPanelProps) {
  const paragraphs = answerParagraphs(answer.answer);

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
                      {claim.source_ids.map((sourceId, sourceIndex) => (
                        <span
                          key={`${sourceId}-${sourceIndex}`}
                          className="inline-flex shrink-0 items-center whitespace-nowrap rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 font-mono text-xs font-medium text-slate-700"
                        >
                          {sourceId}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
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

      <p className="mt-6 text-xs text-slate-500">
        Evidence: {evidenceStatus.replace(/_/g, " ").toLowerCase()} · Sources: {sourceCount}
      </p>
    </section>
  );
}
