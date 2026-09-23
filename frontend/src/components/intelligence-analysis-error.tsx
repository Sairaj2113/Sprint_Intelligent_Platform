import { isAxiosError } from "axios";
import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

type AnalysisErrorPresentation = {
  title: string;
  description: string;
  canRetry: boolean;
  isValidationError: boolean;
  projectMissing: boolean;
};

type IntelligenceAnalysisErrorProps = {
  error: unknown;
  onRetry: () => void;
  retryDisabled?: boolean;
};

export function getAnalysisErrorPresentation(error: unknown): AnalysisErrorPresentation {
  const status = isAxiosError(error) ? error.response?.status : undefined;

  if (status === 422) {
    return {
      title: "Question could not be analyzed",
      description: "Review the question and submit it again.",
      canRetry: false,
      isValidationError: true,
      projectMissing: false,
    };
  }

  if (status === 404) {
    return {
      title: "Project is no longer available",
      description: "Return to Projects and choose an available workspace.",
      canRetry: false,
      isValidationError: false,
      projectMissing: true,
    };
  }

  if (status === 502) {
    return {
      title: "Grounded analysis was unavailable",
      description: "A grounded analysis could not be produced. Please try again.",
      canRetry: true,
      isValidationError: false,
      projectMissing: false,
    };
  }

  if (status === 503) {
    return {
      title: "Analysis service is temporarily unavailable",
      description: "Try again shortly.",
      canRetry: true,
      isValidationError: false,
      projectMissing: false,
    };
  }

  if (isAxiosError(error) && !error.response) {
    return {
      title: "Unable to reach the backend",
      description: "Check your connection and try again.",
      canRetry: true,
      isValidationError: false,
      projectMissing: false,
    };
  }

  return {
    title: "Analysis could not be completed",
    description: "Please try again.",
    canRetry: true,
    isValidationError: false,
    projectMissing: false,
  };
}

export function IntelligenceAnalysisError({
  error,
  onRetry,
  retryDisabled = false,
}: IntelligenceAnalysisErrorProps) {
  const presentation = getAnalysisErrorPresentation(error);

  return (
    <section
      className="rounded-xl border border-rose-200 bg-rose-50 p-5 shadow-sm"
      role="alert"
      aria-labelledby="intelligence-analysis-error-heading"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-rose-700" aria-hidden="true" />
        <div>
          <h2 id="intelligence-analysis-error-heading" className="text-base font-semibold text-rose-950">
            {presentation.title}
          </h2>
          <p id="intelligence-analysis-error-description" className="mt-1 text-sm leading-6 text-rose-800">
            {presentation.description}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            {presentation.canRetry ? (
              <button
                type="button"
                onClick={onRetry}
                disabled={retryDisabled}
                className="inline-flex h-9 items-center rounded-md bg-rose-700 px-3.5 text-sm font-medium text-white transition hover:bg-rose-800 focus:outline-none focus:ring-2 focus:ring-rose-300 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                Try again
              </button>
            ) : null}
            {presentation.projectMissing ? (
              <Link
                to="/projects"
                className="inline-flex h-9 items-center rounded-md border border-rose-200 bg-white px-3.5 text-sm font-medium text-rose-800 transition hover:bg-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300 focus:ring-offset-2"
              >
                Return to projects
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
