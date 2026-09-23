import { LoaderCircle } from "lucide-react";

export function IntelligenceAnalysisPending() {
  return (
    <section
      className="mt-6 rounded-xl border border-sky-200 bg-sky-50 px-5 py-4 shadow-sm sm:px-6"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="flex items-center gap-3">
        <LoaderCircle className="size-5 animate-spin text-sky-700" aria-hidden="true" />
        <div>
          <h2 className="text-sm font-semibold text-slate-950">Analyzing project evidence</h2>
          <p className="mt-1 text-sm text-slate-600">This may take a moment.</p>
        </div>
      </div>
    </section>
  );
}
