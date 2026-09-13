import { CalendarDays } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
import { DurationCards, KpiCards, WorkflowEvidenceTable, WorkflowSummary } from "../components/evidence-ui";
import { IssueDetailsDrawer } from "../components/issue-details-drawer";
import { StatusBadge } from "../components/status-badge";
import { useSprintKpis, useSprintWorkflow } from "../hooks/use-evidence";
import { useProjectIssues } from "../hooks/use-issues";
import { useProjectSprints } from "../hooks/use-projects";
import type { Sprint } from "../types/api";

function formatDate(value: string | null) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function formatTimestamp(value: string | null) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function defaultSprintId(sprints: Sprint[]) {
  return sprints.find((sprint) => sprint.status === "ACTIVE")?.id ?? [...sprints].sort((a, b) => (b.end_date ?? b.start_date ?? "").localeCompare(a.end_date ?? a.start_date ?? ""))[0]?.id;
}

export function ProjectSprintsPage() {
  const { projectKey } = useParams();
  const [selectedSprintId, setSelectedSprintId] = useState<string | null>(null);
  const [selectedIssueKey, setSelectedIssueKey] = useState<string | null>(null);
  const sprintsQuery = useProjectSprints(projectKey);
  const issuesQuery = useProjectIssues(projectKey);
  const sprints = sprintsQuery.data ?? [];
  const fallbackSprintId = useMemo(() => defaultSprintId(sprints), [sprints]);
  const activeSprintId = selectedSprintId ?? fallbackSprintId;
  const selectedSprint = sprints.find((sprint) => sprint.id === activeSprintId);
  const kpisQuery = useSprintKpis(projectKey, activeSprintId);
  const workflowQuery = useSprintWorkflow(projectKey, activeSprintId);
  const sprintIssues = (issuesQuery.data ?? []).filter((issue) => issue.sprint_id === activeSprintId);

  if (sprintsQuery.isPending) return <LoadingState title="Loading sprint overview" />;
  if (sprintsQuery.isError) return <ErrorState title="Sprint overview could not be loaded" description="Sprint data could not be retrieved. Check that the backend is available and try again." />;
  if (!selectedSprint) return <section className="w-full"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">{projectKey ?? "Project"} / Sprints</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Sprint overview</h1><div className="mt-7 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center text-sm text-slate-500">No sprints found for this project.</div></section>;

  const tabClassName = ({ isActive }: { isActive: boolean }) => `inline-flex items-center border-b-2 px-1 py-3 text-sm font-medium transition ${isActive ? "border-sky-600 text-sky-700" : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"}`;
  return <>
    <section className="w-full"><header><p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">{projectKey ?? "Project"} / Sprints</p><div className="mt-2 flex flex-wrap items-center gap-3"><h1 className="text-3xl font-semibold tracking-tight text-slate-950">Sprint overview</h1><StatusBadge status={selectedSprint.status} /></div><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{selectedSprint.goal ?? "No sprint goal has been recorded."}</p><div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500"><span>Planned: {formatDate(selectedSprint.start_date)} - {formatDate(selectedSprint.end_date)}</span><span>Started: {formatTimestamp(selectedSprint.started_at)}</span><span>Completed: {formatTimestamp(selectedSprint.completed_at)}</span></div></header>
      <nav className="mt-6 flex gap-5 overflow-x-auto border-b border-slate-200" aria-label="Project navigation"><NavLink end to={`/projects/${projectKey}`} className={tabClassName}>Overview</NavLink><NavLink to={`/projects/${projectKey}/board`} className={tabClassName}>Board</NavLink><NavLink to={`/projects/${projectKey}/sprints`} className={tabClassName}>Sprints</NavLink><Link to={`/projects/${projectKey}/reports`} className="inline-flex items-center border-b-2 border-transparent px-1 py-3 text-sm font-medium text-slate-500 hover:border-slate-300 hover:text-slate-800">Reports</Link></nav>
      <div className="mt-6 flex gap-2 overflow-x-auto pb-1">{sprints.map((sprint) => <button key={sprint.id} type="button" onClick={() => setSelectedSprintId(sprint.id)} className={`min-w-52 rounded-lg border p-3 text-left transition ${sprint.id === activeSprintId ? "border-sky-300 bg-sky-50 ring-2 ring-sky-100" : "border-slate-200 bg-white hover:border-sky-200"}`}><div className="flex items-start justify-between gap-3"><span className="text-sm font-semibold text-slate-800">{sprint.name}</span><StatusBadge status={sprint.status} /></div><p className="mt-2 text-xs text-slate-500">{formatDate(sprint.start_date)} - {formatDate(sprint.end_date)}</p></button>)}</div>
      <div className="mt-6">{kpisQuery.isPending ? <LoadingState title="Loading sprint KPIs" /> : kpisQuery.isError || !kpisQuery.data ? <ErrorState title="Unable to load sprint KPIs." /> : <><KpiCards kpis={kpisQuery.data} title="Sprint KPI summary" /><DurationCards durations={kpisQuery.data.duration_metrics} /></>}</div>
      <div>{workflowQuery.isPending ? <div className="mt-6"><LoadingState title="Loading sprint workflow evidence" /></div> : workflowQuery.isError || !workflowQuery.data ? <div className="mt-6"><ErrorState title="Unable to load sprint workflow evidence." /></div> : <><WorkflowSummary summary={workflowQuery.data.summary} /><WorkflowEvidenceTable issues={workflowQuery.data.issues} onSelectIssue={setSelectedIssueKey} /></>}</div>
      <section className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center gap-2 border-b border-slate-200 p-5"><CalendarDays className="size-5 text-sky-700" /><div><h2 className="font-semibold text-slate-950">Sprint issues</h2><p className="text-sm text-slate-500">Issues assigned to {selectedSprint.name}</p></div></div>{issuesQuery.isPending ? <div className="p-5"><LoadingState title="Loading sprint issues" /></div> : issuesQuery.isError ? <div className="p-5"><ErrorState title="Unable to load sprint issues." /></div> : sprintIssues.length ? <div className="overflow-x-auto"><table className="w-full min-w-[42rem] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Issue</th><th className="px-5 py-3">Type</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Assignee</th><th className="px-5 py-3 text-right">Points</th></tr></thead><tbody className="divide-y divide-slate-100">{sprintIssues.map((issue) => <tr key={issue.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelectedIssueKey(issue.issue_key)}><td className="px-5 py-3"><p className="font-mono text-xs text-slate-500">{issue.issue_key}</p><p className="font-medium text-slate-800">{issue.title}</p></td><td className="px-5 py-3 text-slate-600">{issue.issue_type.toLowerCase()}</td><td className="px-5 py-3"><StatusBadge status={issue.status} /></td><td className="px-5 py-3 text-slate-600">{issue.assignee?.name ?? "Unassigned"}</td><td className="px-5 py-3 text-right">{issue.story_points ?? "-"}</td></tr>)}</tbody></table></div> : <p className="p-6 text-center text-sm text-slate-500">No issues assigned to this sprint.</p>}</section>
    </section><IssueDetailsDrawer issueKey={selectedIssueKey} onClose={() => setSelectedIssueKey(null)} /></>;
}
