type IntelligenceQuestionFormProps = {
  question: string;
  onQuestionChange: (question: string) => void;
  onAnalyze?: (question: string) => void;
  isAnalyzing?: boolean;
};

export function IntelligenceQuestionForm({
  question,
  onQuestionChange,
  onAnalyze,
  isAnalyzing = false,
}: IntelligenceQuestionFormProps) {
  const canAnalyze = Boolean(question.trim());

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canAnalyze && !isAnalyzing) {
      onAnalyze?.(question);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div>
        <h2 className="text-base font-semibold text-slate-950">Ask about this project</h2>
        <p id="intelligence-question-help" className="mt-1 text-sm leading-6 text-slate-600">
          Ask about requirements, sprint work, testing, deployments, or documented contributions.
        </p>
      </div>
      <form className="mt-4" onSubmit={handleSubmit}>
        <label htmlFor="intelligence-question" className="sr-only">
          Project intelligence question
        </label>
        <textarea
          id="intelligence-question"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          aria-describedby="intelligence-question-help"
          placeholder="Ask a question about this project's evidence..."
          rows={4}
          className="w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm leading-6 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        />
        <div className="mt-3 flex justify-end">
          <button
            type="submit"
            disabled={!canAnalyze || isAnalyzing}
            className="inline-flex h-9 items-center rounded-md bg-sky-700 px-3.5 text-sm font-medium text-white transition hover:bg-sky-800 focus:outline-none focus:ring-2 focus:ring-sky-300 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isAnalyzing ? "Analyzing..." : "Analyze"}
          </button>
        </div>
      </form>
    </section>
  );
}
