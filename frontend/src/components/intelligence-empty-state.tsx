import { FileSearch } from "lucide-react";

const exampleQuestions = [
  "What was completed in the latest sprint?",
  "What testing evidence supports the completed work?",
  "What contributions are documented for this project?",
  "What deployment evidence is available?",
] as const;

type IntelligenceEmptyStateProps = {
  onSelectQuestion: (question: string) => void;
};

export function IntelligenceEmptyState({
  onSelectQuestion,
}: IntelligenceEmptyStateProps) {
  return (
    <section className="mt-6 rounded-xl border border-dashed border-slate-300 bg-white px-5 py-8 text-center shadow-sm sm:px-8 sm:py-10">
      <div className="mx-auto grid size-10 place-items-center rounded-full bg-sky-50 text-sky-700">
        <FileSearch className="size-5" aria-hidden="true" />
      </div>
      <h2 className="mt-4 text-base font-semibold text-slate-950">Explore project evidence</h2>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-600">
        Ask a question to analyze evidence from issues, tests, deployments, comments, and project documents.
      </p>
      <div className="mx-auto mt-6 grid max-w-3xl gap-2 text-left sm:grid-cols-2">
        {exampleQuestions.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onSelectQuestion(example)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-left text-sm text-slate-700 transition hover:border-sky-300 hover:bg-sky-50 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-200"
          >
            {example}
          </button>
        ))}
      </div>
    </section>
  );
}
