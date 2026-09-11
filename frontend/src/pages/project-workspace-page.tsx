import {
  Bug,
  CalendarDays,
  CheckCircle2,
  CircleDot,
  ClipboardList,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
import { IssueDetailsDrawer } from "../components/issue-details-drawer";
import { StatusBadge } from "../components/status-badge";
import { useProjectIssues } from "../hooks/use-issues";
import {
  useProject,
  useProjectMembers,
  useProjectSprints,
} from "../hooks/use-projects";
import type { Issue, IssueStatus } from "../types/api";

type MetricCardProps = {
  label: string;
  value: string | number;
  detail: string;
  icon: LucideIcon;
  tone: string;
};

const trackedStatuses = ["TODO", "IN_PROGRESS", "CODE_REVIEW", "TESTING", "DONE"] as const satisfies readonly IssueStatus[];

const statusLabels: Record<(typeof trackedStatuses)[number], string> = {
  TODO: "To Do",
  IN_PROGRESS: "In Progress",
  CODE_REVIEW: "Code Review",
  TESTING: "Testing",
  DONE: "Done",
};

const priorityOrder: Record<Issue["priority"], number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

const priorityStyles: Record<Issue["priority"], string> = {
  LOW: "bg-slate-100 text-slate-700",
  MEDIUM: "bg-sky-50 text-sky-700",
  HIGH: "bg-amber-50 text-amber-700",
  CRITICAL: "bg-rose-50 text-rose-700",
};

function formatDate(value: string | null) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function memberInitials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function MetricCard({ label, value, detail, icon: Icon, tone }: MetricCardProps) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
          <p className="mt-1 text-xs text-slate-500">{detail}</p>
        </div>
        <div className={`grid size-9 place-items-center rounded-lg ${tone}`}>
          <Icon className="size-4" />
        </div>
      </div>
    </article>
  );
}

export function ProjectWorkspacePage() {
  const { projectKey } = useParams();
  const [selectedIssueKey, setSelectedIssueKey] = useState<string | null>(null);
  const projectQuery = useProject(projectKey);
  const membersQuery = useProjectMembers(projectKey);
  const sprintsQuery = useProjectSprints(projectKey);
  const issuesQuery = useProjectIssues(projectKey);
  const members = membersQuery.data ?? [];
  const sprints = sprintsQuery.data ?? [];
  const issues = issuesQuery.data ?? [];

  const delivery = useMemo(() => {
    const statusCounts: Record<(typeof trackedStatuses)[number], number> = {
      TODO: 0,
      IN_PROGRESS: 0,
      CODE_REVIEW: 0,
      TESTING: 0,
      DONE: 0,
    };
    const issuesBySprint = new Map<string, Issue[]>();
    const issuesByAssignee = new Map<string, Issue[]>();
    let completedIssues = 0;
    let totalStoryPoints = 0;
    let completedStoryPoints = 0;
    let totalBugs = 0;
    let resolvedBugs = 0;

    for (const issue of issues) {
      if (issue.status === "DONE") completedIssues += 1;
      if (issue.status in statusCounts) statusCounts[issue.status as keyof typeof statusCounts] += 1;
      if (issue.story_points !== null) {
        totalStoryPoints += issue.story_points;
        if (issue.status === "DONE") completedStoryPoints += issue.story_points;
      }
      if (issue.issue_type === "BUG") {
        totalBugs += 1;
        if (issue.status === "DONE") resolvedBugs += 1;
      }
      if (issue.sprint_id) {
        const sprintIssues = issuesBySprint.get(issue.sprint_id) ?? [];
        sprintIssues.push(issue);
        issuesBySprint.set(issue.sprint_id, sprintIssues);
      }
      if (issue.assignee_id) {
        const assigneeIssues = issuesByAssignee.get(issue.assignee_id) ?? [];
        assigneeIssues.push(issue);
        issuesByAssignee.set(issue.assignee_id, assigneeIssues);
      }
    }

    const sprintProgress = sprints.map((sprint) => {
      const sprintIssues = issuesBySprint.get(sprint.id) ?? [];
      const completed = sprintIssues.filter((issue) => issue.status === "DONE").length;
      const points = sprintIssues.reduce((total, issue) => total + (issue.story_points ?? 0), 0);
      const completedPoints = sprintIssues.reduce(
        (total, issue) => total + (issue.status === "DONE" ? (issue.story_points ?? 0) : 0),
        0,
      );
      return {
        sprint,
        totalIssues: sprintIssues.length,
        completedIssues: completed,
        completionPercentage: sprintIssues.length ? Math.round((completed / sprintIssues.length) * 100) : 0,
        totalStoryPoints: points,
        completedStoryPoints: completedPoints,
      };
    });

    const contributions = members.map(({ employee }) => {
      const assignedIssues = issuesByAssignee.get(employee.id) ?? [];
      const assignedStoryPoints = assignedIssues.reduce((total, issue) => total + (issue.story_points ?? 0), 0);
      const completedIssueCount = assignedIssues.filter((issue) => issue.status === "DONE").length;
      const completedPoints = assignedIssues.reduce(
        (total, issue) => total + (issue.status === "DONE" ? (issue.story_points ?? 0) : 0),
        0,
      );
      return { employee, assignedIssues, assignedStoryPoints, completedIssueCount, completedPoints };
    });

    const openIssues = issues
      .map((issue, index) => ({ issue, index }))
      .filter(({ issue }) => issue.status !== "DONE")
      .sort((left, right) => priorityOrder[left.issue.priority] - priorityOrder[right.issue.priority] || left.index - right.index)
      .slice(0, 10)
      .map(({ issue }) => issue);

    return {
      statusCounts,
      completedIssues,
      openIssuesCount: issues.length - completedIssues,
      completionPercentage: issues.length ? Math.round((completedIssues / issues.length) * 100) : 0,
      totalStoryPoints,
      completedStoryPoints,
      remainingStoryPoints: totalStoryPoints - completedStoryPoints,
      totalBugs,
      resolvedBugs,
      openBugs: totalBugs - resolvedBugs,
      sprintProgress,
      contributions,
      openIssues,
    };
  }, [issues, members, sprints]);

  if (projectQuery.isPending || membersQuery.isPending || sprintsQuery.isPending || issuesQuery.isPending) {
    return <LoadingState title="Loading project delivery dashboard" />;
  }

  if (projectQuery.isError || membersQuery.isError || sprintsQuery.isError || issuesQuery.isError || !projectQuery.data) {
    return (
      <ErrorState
        title="Project delivery dashboard could not be loaded"
        description="Project, member, sprint, or issue data could not be retrieved. Check that the backend is available and try again."
      />
    );
  }

  const project = projectQuery.data;
  const tabClassName = ({ isActive }: { isActive: boolean }) =>
    `inline-flex items-center border-b-2 px-1 py-3 text-sm font-medium transition ${
      isActive
        ? "border-sky-600 text-sky-700"
        : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"
    }`;

  return (
    <>
      <section className="w-full">
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
            Project / {project.project_key}
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{project.name}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            {project.description ?? "No project description has been provided."}
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <StatusBadge status={project.status} />
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize text-slate-700">
              {(project.methodology ?? "Not set").replace(/_/g, " ").toLowerCase()}
            </span>
            <span className="text-sm text-slate-600">
              Project lead: <strong className="font-medium text-slate-800">{project.project_lead?.name ?? "Unassigned"}</strong>
            </span>
          </div>
        </header>

        <nav className="mt-7 flex gap-5 overflow-x-auto border-b border-slate-200" aria-label="Project navigation">
          <NavLink end to={`/projects/${project.project_key}`} className={tabClassName}>Overview</NavLink>
          <NavLink to={`/projects/${project.project_key}/board`} className={tabClassName}>Board</NavLink>
          <NavLink to={`/projects/${project.project_key}/sprints`} className={tabClassName}>Sprints</NavLink>
          <Link to={`/projects/${project.project_key}/reports`} className="inline-flex items-center border-b-2 border-transparent px-1 py-3 text-sm font-medium text-slate-500 hover:border-slate-300 hover:text-slate-800">Reports</Link>
        </nav>

        <section className="mt-7">
          <div className="flex items-end justify-between gap-4"><div><h2 className="text-lg font-semibold text-slate-950">Delivery overview</h2><p className="mt-1 text-sm text-slate-500">Factual delivery counts from documented project issues.</p></div><span className="text-sm font-semibold text-slate-700">Issue completion: {delivery.completionPercentage}%</span></div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total issues" value={issues.length} detail="Documented project work" icon={ClipboardList} tone="bg-sky-50 text-sky-700" />
            <MetricCard label="Completed issues" value={delivery.completedIssues} detail={`${delivery.completionPercentage}% issue completion`} icon={CheckCircle2} tone="bg-emerald-50 text-emerald-700" />
            <MetricCard label="Open issues" value={delivery.openIssuesCount} detail="Not in Done status" icon={CircleDot} tone="bg-amber-50 text-amber-700" />
            <MetricCard label="Total sprints" value={sprints.length} detail="Project sprint records" icon={CalendarDays} tone="bg-violet-50 text-violet-700" />
          </div>
          <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between gap-4"><div><h3 className="font-semibold text-slate-950">Issue completion</h3><p className="mt-1 text-sm text-slate-500">Completed issues out of all project issues</p></div><span className="text-2xl font-semibold text-slate-950">{delivery.completionPercentage}%</span></div><div className="mt-5 h-3 overflow-hidden rounded-full bg-slate-100"><div className="rounded-full transition-all" style={{ width: `${delivery.completionPercentage}%`, height: "100%", backgroundColor: "#10b981" }} /></div><div className="mt-3 flex flex-wrap justify-between gap-2 text-xs text-slate-500"><span>{delivery.completedIssues} completed of {issues.length} issues</span><span>Story points: {delivery.completedStoryPoints} completed / {delivery.totalStoryPoints} total / {delivery.remainingStoryPoints} remaining</span></div></div>
        </section>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="font-semibold text-slate-950">Issue status distribution</h2>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
              {trackedStatuses.map((status) => <div key={status} className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-medium text-slate-500">{statusLabels[status]}</p><p className="mt-1 text-xl font-semibold text-slate-900">{delivery.statusCounts[status]}</p></div>)}
            </div>
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="font-semibold text-slate-950">Project quality summary</h2>
            <p className="mt-1 text-sm text-slate-500">Issue-derived quality indicators</p>
            <dl className="mt-5 grid grid-cols-2 gap-3 text-sm"><div className="rounded-lg bg-slate-50 p-3"><dt className="text-slate-500">Total bugs</dt><dd className="mt-1 text-xl font-semibold text-slate-900">{delivery.totalBugs}</dd></div><div className="rounded-lg bg-slate-50 p-3"><dt className="text-slate-500">Resolved bugs</dt><dd className="mt-1 text-xl font-semibold text-slate-900">{delivery.resolvedBugs}</dd></div><div className="rounded-lg bg-slate-50 p-3"><dt className="text-slate-500">Open bugs</dt><dd className="mt-1 text-xl font-semibold text-slate-900">{delivery.openBugs}</dd></div><div className="rounded-lg bg-slate-50 p-3"><dt className="text-slate-500">Issues in testing</dt><dd className="mt-1 text-xl font-semibold text-slate-900">{delivery.statusCounts.TESTING}</dd></div><div className="col-span-2 rounded-lg bg-slate-50 p-3"><dt className="text-slate-500">Issues in code review</dt><dd className="mt-1 text-xl font-semibold text-slate-900">{delivery.statusCounts.CODE_REVIEW}</dd></div></dl>
          </section>
        </div>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center gap-2"><CalendarDays className="size-5 text-sky-700" /><div><h2 className="font-semibold text-slate-950">Sprint progress</h2><p className="text-sm text-slate-500">Issue and story-point completion for each project sprint</p></div></div><div className="mt-5 grid gap-4 lg:grid-cols-2">{delivery.sprintProgress.map(({ sprint, totalIssues, completedIssues, completionPercentage, completedStoryPoints, totalStoryPoints }) => <article key={sprint.id} className="rounded-lg border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-slate-800">{sprint.name}</h3><p className="mt-1 text-xs text-slate-500">{sprint.goal ?? "No sprint goal recorded."}</p></div><StatusBadge status={sprint.status} /></div><div className="mt-4 flex justify-between text-xs text-slate-500"><span>{completedIssues} of {totalIssues} issues completed</span><span>{completionPercentage}%</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="rounded-full transition-all" style={{ width: `${completionPercentage}%`, height: "100%", backgroundColor: "#0ea5e9" }} /></div><p className="mt-3 text-xs text-slate-500">Story points: {completedStoryPoints} / {totalStoryPoints} completed</p></article>)}</div>{!sprints.length ? <p className="mt-5 text-sm text-slate-500">No sprints have been recorded for this project.</p> : null}</section>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-200 p-5"><h2 className="font-semibold text-slate-950">Recent open work</h2><p className="mt-1 text-sm text-slate-500">Up to ten open issues, ordered by priority.</p></div>{delivery.openIssues.length ? <div className="divide-y divide-slate-100">{delivery.openIssues.map((issue) => <button key={issue.id} type="button" onClick={() => setSelectedIssueKey(issue.issue_key)} className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-slate-50"><div className="min-w-0 flex-1"><p className="font-mono text-xs text-slate-500">{issue.issue_key}</p><p className="truncate text-sm font-medium text-slate-800">{issue.title}</p><p className="mt-1 text-xs text-slate-500">{issue.assignee?.name ?? "Unassigned"} · {issue.sprint?.name ?? "No sprint"}</p></div><div className="flex shrink-0 flex-col items-end gap-1"><StatusBadge status={issue.status} /><span className={`rounded px-2 py-1 text-xs font-semibold ${priorityStyles[issue.priority]}`}>{issue.priority.toLowerCase()}</span></div></button>)}</div> : <p className="p-6 text-center text-sm text-slate-500">No open issues in this project.</p>}</section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center gap-2"><UsersRound className="size-5 text-sky-700" /><div><h2 className="font-semibold text-slate-950">Project members</h2><p className="text-sm text-slate-500">Current project membership</p></div></div><div className="mt-4 divide-y divide-slate-100">{members.map(({ employee }) => <div key={employee.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"><div className="grid size-9 shrink-0 place-items-center rounded-full bg-sky-100 text-xs font-bold text-sky-800">{memberInitials(employee.name)}</div><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-800">{employee.name}</p><p className="text-xs text-slate-500">{employee.employee_code} · {employee.role ?? "Team member"}</p></div><p className="ml-auto hidden text-xs text-slate-500 sm:block">{employee.department ?? ""}</p></div>)}</div>{!members.length ? <p className="mt-4 text-sm text-slate-500">No project members have been recorded.</p> : null}</section>
        </div>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-200 p-5"><h2 className="font-semibold text-slate-950">Contribution snapshot</h2><p className="mt-1 text-sm text-slate-500">Counts reflect documented issue assignments and completion only; they are not performance ratings.</p></div>{delivery.contributions.length ? <div className="overflow-x-auto"><table className="w-full min-w-[48rem] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 font-medium">Team member</th><th className="px-5 py-3 text-right font-medium">Assigned issues</th><th className="px-5 py-3 text-right font-medium">Completed issues</th><th className="px-5 py-3 text-right font-medium">Assigned points</th><th className="px-5 py-3 text-right font-medium">Completed points</th></tr></thead><tbody className="divide-y divide-slate-100">{delivery.contributions.map(({ employee, assignedIssues, completedIssueCount, assignedStoryPoints, completedPoints }) => <tr key={employee.id}><td className="px-5 py-3"><p className="font-medium text-slate-800">{employee.name}</p><p className="text-xs text-slate-500">{employee.role ?? "Team member"}</p></td><td className="px-5 py-3 text-right text-slate-700">{assignedIssues.length}</td><td className="px-5 py-3 text-right text-slate-700">{completedIssueCount}</td><td className="px-5 py-3 text-right text-slate-700">{assignedStoryPoints}</td><td className="px-5 py-3 text-right text-slate-700">{completedPoints}</td></tr>)}</tbody></table></div> : <p className="p-6 text-center text-sm text-slate-500">No project members have been recorded.</p>}</section>
      </section>

      <IssueDetailsDrawer issueKey={selectedIssueKey} onClose={() => setSelectedIssueKey(null)} />
    </>
  );
}
