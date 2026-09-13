import { UsersRound } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
import { DurationCards, KpiCards, WorkflowEvidenceTable, WorkflowSummary, formatHours } from "../components/evidence-ui";
import { IssueDetailsDrawer } from "../components/issue-details-drawer";
import { StatusBadge } from "../components/status-badge";
import { useEmployeeContribution, useProjectKpis, useProjectWorkflow } from "../hooks/use-evidence";
import { useProject, useProjectMembers } from "../hooks/use-projects";
import type { Employee } from "../types/api";

function initials(name: string) {
  return name.split(" ").filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function ContributionRow({ projectKey, employee, onSelect }: { projectKey: string; employee: Employee; onSelect: () => void }) {
  const query = useEmployeeContribution(projectKey, employee.id);
  if (query.isPending) return <div className="border-t border-slate-100 px-5 py-3 text-sm text-slate-500">Loading contribution evidence for {employee.name}…</div>;
  if (query.isError || !query.data) return <div className="border-t border-slate-100 px-5 py-3 text-sm text-rose-700">Unable to load contribution evidence for {employee.name}.</div>;
  const summary = query.data.summary;
  return <button type="button" onClick={onSelect} className="grid w-full grid-cols-[minmax(11rem,1fr)_repeat(6,auto)] items-center gap-4 border-t border-slate-100 px-5 py-3 text-left hover:bg-slate-50"><span><span className="font-medium text-slate-800">{employee.name}</span><span className="block text-xs text-slate-500">{employee.role ?? "Team member"}</span></span><span className="text-right text-sm text-slate-700">{summary.assigned_issues} assigned</span><span className="text-right text-sm text-slate-700">{summary.completed_issues} completed</span><span className="text-right text-sm text-slate-700">{summary.completed_story_points} / {summary.assigned_story_points} points</span><span className="text-right text-sm text-slate-700">{summary.issues_reaching_testing} testing</span><span className="text-right text-sm text-slate-700">{summary.issues_deployed} deployed</span><span className="text-right text-sm text-slate-700">{summary.issues_commented_on} commented</span></button>;
}

export function ProjectWorkspacePage() {
  const { projectKey } = useParams();
  const [selectedIssueKey, setSelectedIssueKey] = useState<string | null>(null);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const projectQuery = useProject(projectKey);
  const membersQuery = useProjectMembers(projectKey);
  const kpisQuery = useProjectKpis(projectKey);
  const workflowQuery = useProjectWorkflow(projectKey);
  const contributionQuery = useEmployeeContribution(projectKey, selectedEmployeeId ?? undefined);

  if (projectQuery.isPending) return <LoadingState title="Loading project workspace" />;
  if (projectQuery.isError || !projectQuery.data) return <ErrorState title="Project workspace could not be loaded" description="The project may not exist, or the backend service is unavailable." />;

  const project = projectQuery.data;
  const members = membersQuery.data ?? [];
  const selectedMember = members.find((member) => member.employee.id === selectedEmployeeId)?.employee;
  const tabClassName = ({ isActive }: { isActive: boolean }) => `inline-flex items-center border-b-2 px-1 py-3 text-sm font-medium transition ${isActive ? "border-sky-600 text-sky-700" : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"}`;

  return <>
    <section className="w-full">
      <header><p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">Project / {project.project_key}</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{project.name}</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{project.description ?? "No project description has been provided."}</p><div className="mt-5 flex flex-wrap items-center gap-2"><StatusBadge status={project.status} /><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize text-slate-700">{(project.methodology ?? "Not set").toLowerCase()}</span><span className="text-sm text-slate-600">Project lead: <strong className="font-medium text-slate-800">{project.project_lead?.name ?? "Unassigned"}</strong></span></div></header>
      <nav className="mt-7 flex gap-5 overflow-x-auto border-b border-slate-200" aria-label="Project navigation"><NavLink end to={`/projects/${project.project_key}`} className={tabClassName}>Overview</NavLink><NavLink to={`/projects/${project.project_key}/board`} className={tabClassName}>Board</NavLink><NavLink to={`/projects/${project.project_key}/sprints`} className={tabClassName}>Sprints</NavLink><Link to={`/projects/${project.project_key}/reports`} className="inline-flex items-center border-b-2 border-transparent px-1 py-3 text-sm font-medium text-slate-500 hover:border-slate-300 hover:text-slate-800">Reports</Link></nav>

      <div className="mt-7">{kpisQuery.isPending ? <LoadingState title="Loading project KPIs" /> : kpisQuery.isError || !kpisQuery.data ? <ErrorState title="Unable to load project KPIs." /> : <><KpiCards kpis={kpisQuery.data} title="Project KPI summary" /><DurationCards durations={kpisQuery.data.duration_metrics} /></>}</div>
      <div>{workflowQuery.isPending ? <div className="mt-6"><LoadingState title="Loading workflow evidence" /></div> : workflowQuery.isError || !workflowQuery.data ? <div className="mt-6"><ErrorState title="Unable to load workflow evidence." /></div> : <><WorkflowSummary summary={workflowQuery.data.summary} /><WorkflowEvidenceTable issues={workflowQuery.data.issues} onSelectIssue={setSelectedIssueKey} /></>}</div>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center gap-2 border-b border-slate-200 p-5"><UsersRound className="size-5 text-sky-700" /><div><h2 className="font-semibold text-slate-950">Team contribution evidence</h2><p className="text-sm text-slate-500">Counts reflect documented assignments and completion only; they are not performance ratings.</p></div></div>{membersQuery.isPending ? <div className="p-5"><LoadingState title="Loading project members" /></div> : membersQuery.isError ? <div className="p-5"><ErrorState title="Unable to load project members." /></div> : members.length ? <div className="overflow-x-auto"><div className="min-w-[48rem]">{members.map(({ employee }) => <ContributionRow key={employee.id} projectKey={project.project_key} employee={employee} onSelect={() => setSelectedEmployeeId(employee.id)} />)}</div></div> : <p className="p-6 text-center text-sm text-slate-500">No project members have been recorded.</p>}</section>

      {selectedMember ? <section className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-200 p-5"><div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-full bg-sky-100 text-xs font-bold text-sky-800">{initials(selectedMember.name)}</div><div><h2 className="font-semibold text-slate-950">{selectedMember.name} — issue evidence</h2><p className="text-sm text-slate-500">Assigned issues and their documented workflow evidence.</p></div></div></div>{contributionQuery.isPending ? <div className="p-5"><LoadingState title="Loading employee contribution evidence" /></div> : contributionQuery.isError || !contributionQuery.data ? <div className="p-5"><ErrorState title="Unable to load contribution evidence." /></div> : contributionQuery.data.issues.length ? <div className="overflow-x-auto"><table className="w-full min-w-[52rem] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Issue</th><th className="px-5 py-3">Sprint</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Points</th><th className="px-5 py-3">Completed</th><th className="px-5 py-3">Reached testing</th><th className="px-5 py-3">Deployment evidence</th><th className="px-5 py-3 text-right">Reopens</th><th className="px-5 py-3 text-right">Cycle time</th></tr></thead><tbody className="divide-y divide-slate-100">{contributionQuery.data.issues.map((issue) => <tr key={issue.issue_id} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelectedIssueKey(issue.issue_key)}><td className="px-5 py-3"><p className="font-mono text-xs text-slate-500">{issue.issue_key}</p><p className="font-medium text-slate-800">{issue.title}</p></td><td className="px-5 py-3 text-slate-600">{issue.sprint_name ?? "No sprint"}</td><td className="px-5 py-3"><StatusBadge status={issue.status} /></td><td className="px-5 py-3 text-right">{issue.story_points ?? "-"}</td><td className="px-5 py-3">{issue.was_completed ? "Yes" : "No"}</td><td className="px-5 py-3">{issue.reached_testing ? "Yes" : "No"}</td><td className="px-5 py-3">{issue.was_deployed ? "Yes" : "No"}</td><td className="px-5 py-3 text-right">{issue.reopen_count}</td><td className="px-5 py-3 text-right">{formatHours(issue.cycle_time_hours)}</td></tr>)}</tbody></table></div> : <p className="p-6 text-center text-sm text-slate-500">No assigned issue evidence is available for this member.</p>}</section> : null}
    </section>
    <IssueDetailsDrawer issueKey={selectedIssueKey} onClose={() => setSelectedIssueKey(null)} />
  </>;
}
