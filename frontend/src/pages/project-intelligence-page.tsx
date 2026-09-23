import { BrainCircuit } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
import {
  getAnalysisErrorPresentation,
  IntelligenceAnalysisError,
} from "../components/intelligence-analysis-error";
import { IntelligenceAnalysisPending } from "../components/intelligence-analysis-pending";
import { EvidenceStatusPanel } from "../components/evidence-status-panel";
import { GroundedAnswerPanel } from "../components/grounded-answer-panel";
import { IntelligenceEmptyState } from "../components/intelligence-empty-state";
import { IntelligenceQuestionForm } from "../components/intelligence-question-form";
import { useAnalyzeProjectIntelligence } from "../hooks/use-project-intelligence";
import { useProject } from "../hooks/use-projects";

type ProjectIntelligenceContentProps = {
  projectKey: string;
  projectName: string;
};

function ProjectIntelligenceContent({
  projectKey,
  projectName,
}: ProjectIntelligenceContentProps) {
  const [question, setQuestion] = useState("");
  const analysisMutation = useAnalyzeProjectIntelligence(projectKey);
  const resultRef = useRef<HTMLDivElement>(null);
  const validationError = analysisMutation.isError
    && getAnalysisErrorPresentation(analysisMutation.error).isValidationError;

  useEffect(() => {
    if (!analysisMutation.isPending && (analysisMutation.isSuccess || analysisMutation.isError)) {
      resultRef.current?.focus();
    }
  }, [analysisMutation.isError, analysisMutation.isPending, analysisMutation.isSuccess]);

  function handleAnalyze(rawQuestion: string) {
    const trimmedQuestion = rawQuestion.trim();
    if (!trimmedQuestion || analysisMutation.isPending) {
      return;
    }
    analysisMutation.mutate({ question: trimmedQuestion });
  }

  function handleQuestionChange(nextQuestion: string) {
    setQuestion(nextQuestion);
    if (analysisMutation.isError) {
      analysisMutation.reset();
    }
  }

  return (
    <>
      <section className="mt-6 rounded-xl border border-slate-200 bg-slate-50 px-5 py-4 sm:px-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Project context</p>
        <p className="mt-1 text-base font-semibold text-slate-900">{projectName}</p>
        <p className="mt-1 font-mono text-xs text-slate-500">{projectKey}</p>
      </section>

      <div className="mt-6">
        <IntelligenceQuestionForm
          question={question}
          onQuestionChange={handleQuestionChange}
          onAnalyze={handleAnalyze}
          isAnalyzing={analysisMutation.isPending}
          hasValidationError={validationError}
          errorMessageId={validationError ? "intelligence-analysis-error-description" : undefined}
        />

        {analysisMutation.isPending ? (
          <IntelligenceAnalysisPending />
        ) : null}

        {analysisMutation.isIdle ? (
          <IntelligenceEmptyState onSelectQuestion={setQuestion} />
        ) : null}

        {!analysisMutation.isPending && analysisMutation.isSuccess && analysisMutation.data.answer ? (
          <div
            ref={resultRef}
            tabIndex={-1}
            role="region"
            aria-label="Analysis result"
            aria-busy="false"
            className="focus:outline-none"
          >
            <GroundedAnswerPanel
              answer={analysisMutation.data.answer}
              question={analysisMutation.data.question}
              evidence={analysisMutation.data.evidence}
              sourceCount={analysisMutation.data.sources.length}
              sources={analysisMutation.data.sources}
              citationValidation={analysisMutation.data.citation_validation}
            />
          </div>
        ) : null}

        {!analysisMutation.isPending && analysisMutation.isSuccess && !analysisMutation.data.answer ? (
          <div
            ref={resultRef}
            tabIndex={-1}
            role="region"
            aria-label="Analysis result"
            aria-busy="false"
            className="focus:outline-none"
          >
            <section className="mt-6 rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-700 shadow-sm">
              <h2 className="font-semibold text-slate-950">Analysis</h2>
              <p className="mt-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                Question
              </p>
              <p className="mt-1 break-words leading-6">{analysisMutation.data.question}</p>
              <EvidenceStatusPanel
                evidence={analysisMutation.data.evidence}
                sourceCount={analysisMutation.data.sources.length}
                citationValidation={analysisMutation.data.citation_validation}
              />
              <p className="mt-5 leading-6">No grounded answer was produced.</p>
            </section>
          </div>
        ) : null}

        {analysisMutation.isError ? (
          <div
            ref={resultRef}
            tabIndex={-1}
            role="region"
            aria-label="Analysis request error"
            className="mt-6 focus:outline-none"
          >
            <IntelligenceAnalysisError
              error={analysisMutation.error}
              onRetry={() => handleAnalyze(question)}
              retryDisabled={!question.trim() || analysisMutation.isPending}
            />
          </div>
        ) : null}
      </div>
    </>
  );
}

export function ProjectIntelligencePage() {
  const { projectKey } = useParams();
  const projectQuery = useProject(projectKey);

  if (projectQuery.isPending) {
    return <LoadingState title="Loading project intelligence" />;
  }

  if (projectQuery.isError || !projectQuery.data) {
    return (
      <ErrorState
        title="Project intelligence could not be loaded"
        description="The project may not exist, or the backend service is unavailable."
      />
    );
  }

  const project = projectQuery.data;

  return (
    <section className="w-full">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
          {project.project_key} / AI Intelligence
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <div className="grid size-10 place-items-center rounded-lg bg-sky-100 text-sky-700">
            <BrainCircuit className="size-5" aria-hidden="true" />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">AI Intelligence</h1>
        </div>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          Ask evidence-grounded questions about this project’s delivery work and documentation.
        </p>
      </header>

      <ProjectIntelligenceContent
        key={project.project_key}
        projectKey={project.project_key}
        projectName={project.name}
      />
    </section>
  );
}
