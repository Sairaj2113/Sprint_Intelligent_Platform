import { BrainCircuit } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
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

  function handleAnalyze(rawQuestion: string) {
    const trimmedQuestion = rawQuestion.trim();
    if (!trimmedQuestion || analysisMutation.isPending) {
      return;
    }
    analysisMutation.mutate({ question: trimmedQuestion });
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
          onQuestionChange={setQuestion}
          onAnalyze={handleAnalyze}
          isAnalyzing={analysisMutation.isPending}
        />

        {analysisMutation.isPending ? (
          <p className="mt-4 text-sm text-slate-600" role="status" aria-live="polite">
            Analysis request in progress.
          </p>
        ) : null}

        {analysisMutation.isIdle ? (
          <IntelligenceEmptyState onSelectQuestion={setQuestion} />
        ) : null}

        {analysisMutation.isSuccess ? (
          <section className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-950 shadow-sm">
            <p className="font-semibold">Analysis received successfully</p>
            <p className="mt-1">
              Evidence status: {analysisMutation.data.evidence.status}
            </p>
            <p>Sources received: {analysisMutation.data.sources.length}</p>
          </section>
        ) : null}

        {analysisMutation.isError ? (
          <div className="mt-6">
            <ErrorState
              title="Unable to analyze project evidence"
              description="Please try again."
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
