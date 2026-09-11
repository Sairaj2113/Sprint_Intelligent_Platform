import { ArrowRight, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
import { PagePlaceholder } from "../components/page-placeholder";
import { StatusBadge } from "../components/status-badge";
import { useProjects } from "../hooks/use-projects";

function formatLabel(value: string | null) {
  return value ? value.replace(/_/g, " ").toLowerCase() : "Not set";
}

export function ProjectsPage() {
  const projectsQuery = useProjects();

  return (
    <PagePlaceholder
      eyebrow="Projects"
      title="Project portfolio"
      description="Explore active delivery workspaces and their project context."
    >
      <div className="mt-7 space-y-3">
        {projectsQuery.isPending && <LoadingState title="Loading projects" />}
        {projectsQuery.isError && (
          <ErrorState
            title="Projects could not be loaded"
            description="The project service is unavailable. Confirm the backend URL and try again."
          />
        )}
        {projectsQuery.data?.map((project) => (
          <Link
            key={project.id}
            to={`/projects/${project.project_key}`}
            className="group block rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:border-sky-300 hover:shadow-md"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-slate-100 px-2 py-1 font-mono text-xs font-semibold text-slate-700">
                    {project.project_key}
                  </span>
                  <StatusBadge status={project.status} />
                </div>
                <h2 className="mt-3 text-lg font-semibold text-slate-950 group-hover:text-sky-700">
                  {project.name}
                </h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                  {project.description ?? "No project description has been provided."}
                </p>
              </div>
              <ArrowRight className="size-5 shrink-0 text-slate-400 transition group-hover:translate-x-1 group-hover:text-sky-600" />
            </div>
            <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 border-t border-slate-100 pt-4 text-sm text-slate-600">
              <span>Methodology: <strong className="font-medium text-slate-800">{formatLabel(project.methodology)}</strong></span>
              <span className="inline-flex items-center gap-1.5">
                <UserRound className="size-4 text-slate-400" />
                Lead: <strong className="font-medium text-slate-800">{project.project_lead?.name ?? "Unassigned"}</strong>
              </span>
            </div>
          </Link>
        ))}
      </div>
    </PagePlaceholder>
  );
}
