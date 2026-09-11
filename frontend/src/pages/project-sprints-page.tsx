import { Bug, CalendarDays, CheckCircle2, CircleDot, ListChecks } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
import { IssueDetailsDrawer } from "../components/issue-details-drawer";
import { StatusBadge } from "../components/status-badge";
import { useProjectIssues } from "../hooks/use-issues";
import { useProjectSprints } from "../hooks/use-projects";
import type { IssueStatus, Sprint } from "../types/api";

type SprintMetric = {
  label: string;
  value: string | number;
  detail: string;
  icon: typeof ListChecks;
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

function formatDate(value: string | null) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatTimestamp(value: string | null) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function getMostRecentSprintId(sprints: Sprint[]) {
  const activeSprint = sprints.find((sprint) => sprint.status === "ACTIVE");
  if (activeSprint) return activeSprint.id;

  return [...sprints]
    .sort((left, right) => {
      const leftDate = left.end_date ?? left.start_date ?? "";
      const rightDate = right.end_date ?? right.start_date ?? "";
      return rightDate.localeCompare(leftDate);
    })
    [0]?.id;
}

function SprintSelector({
  sprints,
  selectedSprintId,
  onSelect,
}: {
  sprints: Sprint[];
  selectedSprintId: string | undefined;
  onSelect: (sprintId: string) => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Sprint selector">
      {sprints.map((sprint) => {
        const isSelected = sprint.id === selectedSprintId;
        return (
          <button
            key={sprint.id}
            type="button"
            onClick={() => onSelect(sprint.id)}
            className={`min-w-52 rounded-lg border p-3 text-left transition ${
              isSelected
                ? "border-sky-300 bg-sky-50 ring-2 ring-sky-100"
                : "border-slate-200 bg-white hover:border-sky-200 hover:bg-slate-50"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <span className="line-clamp-2 text-sm font-semibold text-slate-800">{sprint.name}</span>
              <StatusBadge status={sprint.status} />
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
              {sprint.goal ?? "No sprint goal recorded."}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Planned: {formatDate(sprint.start_date)} - {formatDate(sprint.end_date)}
            </p>
            {sprint.started_at || sprint.completed_at ? (
              <p className="mt-1 text-xs text-slate-500">
                Actual: {sprint.started_at ? `started ${formatTimestamp(sprint.started_at)}` : "not started"}
                {sprint.completed_at ? ` / completed ${formatTimestamp(sprint.completed_at)}` : ""}
              </p>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function MetricCard({ metric }: { metric: SprintMetric }) {
  const Icon = metric.icon;
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{metric.label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{metric.value}</p>
          <p className="mt-1 text-xs text-slate-500">{metric.detail}</p>
        </div>
        <div className={`grid size-9 place-items-center rounded-lg ${metric.tone}`}>
          <Icon className="size-4" />
        </div>
      </div>
    </article>
  );
}

export function ProjectSprintsPage() {
  const { projectKey } = useParams();
  const [selectedSprintId, setSelectedSprintId] = useState<string | null>(null);
  const [selectedIssueKey, setSelectedIssueKey] = useState<string | null>(null);
  const sprintsQuery = useProjectSprints(projectKey);
  const issuesQuery = useProjectIssues(projectKey);
  const sprints = sprintsQuery.data ?? [];
  const issues = issuesQuery.data ?? [];
  const defaultSprintId = useMemo(() => getMostRecentSprintId(sprints), [sprints]);
  const activeSprintId = selectedSprintId ?? defaultSprintId;
  const selectedSprint = sprints.find((sprint) => sprint.id === activeSprintId);
  const sprintIssues = useMemo(
    () => issues.filter((issue) => issue.sprint_id === selectedSprint?.id),
    [issues, selectedSprint?.id],
  );
  const metrics = useMemo(() => {
    const statusCounts = Object.fromEntries(trackedStatuses.map((status) => [status, 0])) as Record<
      (typeof trackedStatuses)[number],
      number
    >;
    let totalStoryPoints = 0;
    let completedStoryPoints = 0;
    let totalBugs = 0;
    let resolvedBugs = 0;
    let overdueIssues = 0;
    const today = new Date().toISOString().slice(0, 10);

    for (const issue of sprintIssues) {
      if (issue.status in statusCounts) {
        statusCounts[issue.status as keyof typeof statusCounts] += 1;
      }
      if (issue.story_points !== null) {
        totalStoryPoints += issue.story_points;
        if (issue.status === "DONE") completedStoryPoints += issue.story_points;
      }
      if (issue.issue_type === "BUG") {
        totalBugs += 1;
        if (issue.status === "DONE") resolvedBugs += 1;
      }
      if (issue.due_date && issue.due_date < today && issue.status !== "DONE") overdueIssues += 1;
    }

    const completedIssues = statusCounts.DONE;
    const completionPercentage = sprintIssues.length
      ? Math.round((completedIssues / sprintIssues.length) * 100)
      : 0;
    const storyPointPercentage = totalStoryPoints
      ? Math.round((completedStoryPoints / totalStoryPoints) * 100)
      : 0;

    return {
      statusCounts,
      completedIssues,
      completionPercentage,
      totalStoryPoints,
      completedStoryPoints,
      storyPointPercentage,
      totalBugs,
      resolvedBugs,
      openBugs: totalBugs - resolvedBugs,
      overdueIssues,
      remainingStoryPoints: totalStoryPoints - completedStoryPoints,
    };
  }, [sprintIssues]);

  if (sprintsQuery.isPending || issuesQuery.isPending) {
    return <LoadingState title="Loading sprint overview" />;
  }

  if (sprintsQuery.isError || issuesQuery.isError) {
    return (
      <ErrorState
        title="Sprint overview could not be loaded"
        description="Sprint or issue data could not be retrieved. Check that the backend is available and try again."
      />
    );
  }

  const tabClassName = ({ isActive }: { isActive: boolean }) =>
    `inline-flex items-center border-b-2 px-1 py-3 text-sm font-medium transition ${
      isActive
        ? "border-sky-600 text-sky-700"
        : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"
    }`;

  if (!sprints.length || !selectedSprint) {
    return (
      <section className="w-full">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
          {projectKey ?? "Project"} / Sprints
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Sprint overview</h1>
        <div className="mt-7 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
          <h2 className="text-base font-semibold text-slate-800">No sprints found for this project</h2>
          <p className="mt-1 text-sm text-slate-500">Sprint-level metrics will appear once a sprint is available.</p>
        </div>
      </section>
    );
  }

  const metricCards: SprintMetric[] = [
    { label: "Total issues", value: sprintIssues.length, detail: `${metrics.completedIssues} completed`, icon: ListChecks, tone: "bg-sky-50 text-sky-700" },
    { label: "Issue completion", value: `${metrics.completionPercentage}%`, detail: "Based on issue count", icon: CheckCircle2, tone: "bg-emerald-50 text-emerald-700" },
    { label: "Story points", value: `${metrics.completedStoryPoints} / ${metrics.totalStoryPoints}`, detail: "Completed / total points", icon: CircleDot, tone: "bg-violet-50 text-violet-700" },
    { label: "Open bugs", value: metrics.openBugs, detail: `${metrics.resolvedBugs} resolved of ${metrics.totalBugs}`, icon: Bug, tone: "bg-rose-50 text-rose-700" },
  ];

  return (
    <>
      <section className="w-full">
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
            {projectKey ?? "Project"} / Sprints
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Sprint overview</h1>
            <StatusBadge status={selectedSprint.status} />
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {selectedSprint.goal ?? "No sprint goal has been recorded."}
          </p>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500">
            <span>Planned: {formatDate(selectedSprint.start_date)} - {formatDate(selectedSprint.end_date)}</span>
            <span>Started: {formatTimestamp(selectedSprint.started_at)}</span>
            <span>Completed: {formatTimestamp(selectedSprint.completed_at)}</span>
          </div>
        </header>

        <nav className="mt-6 flex gap-5 overflow-x-auto border-b border-slate-200" aria-label="Project navigation">
          <NavLink end to={`/projects/${projectKey}`} className={tabClassName}>Overview</NavLink>
          <NavLink to={`/projects/${projectKey}/board`} className={tabClassName}>Board</NavLink>
          <NavLink to={`/projects/${projectKey}/sprints`} className={tabClassName}>Sprints</NavLink>
          <Link to={`/projects/${projectKey}/reports`} className="inline-flex items-center border-b-2 border-transparent px-1 py-3 text-sm font-medium text-slate-500 hover:border-slate-300 hover:text-slate-800">Reports</Link>
        </nav>

        <div className="mt-6">
          <SprintSelector sprints={sprints} selectedSprintId={activeSprintId} onSelect={setSelectedSprintId} />
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metricCards.map((metric) => <MetricCard key={metric.label} metric={metric} />)}
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div><h2 className="font-semibold text-slate-950">Issue completion</h2><p className="mt-1 text-sm text-slate-500">Completed issues out of all sprint issues</p></div>
              <span className="text-2xl font-semibold text-slate-950">{metrics.completionPercentage}%</span>
            </div>
            <div className="mt-5 h-3 overflow-hidden rounded-full bg-slate-100" aria-label={`${metrics.completionPercentage}% issue completion`}>
              <div className="rounded-full transition-all" style={{ width: `${metrics.completionPercentage}%`, height: "100%", backgroundColor: "#10b981" }} />
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-500"><span>{metrics.completedIssues} completed</span><span>{sprintIssues.length} total issues</span></div>
            <div className="mt-6 border-t border-slate-100 pt-5">
              <div className="flex items-center justify-between gap-3"><div><h3 className="text-sm font-semibold text-slate-800">Story point completion</h3><p className="mt-1 text-xs text-slate-500">Completed {metrics.completedStoryPoints} / {metrics.totalStoryPoints} story points</p></div><span className="text-sm font-semibold text-slate-700">{metrics.storyPointPercentage}%</span></div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"><div className="rounded-full" style={{ width: `${metrics.storyPointPercentage}%`, height: "100%", backgroundColor: "#8b5cf6" }} /></div>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="font-semibold text-slate-950">Sprint health</h2>
            <p className="mt-1 text-sm text-slate-500">Factual indicators from current issue data</p>
            <dl className="mt-5 space-y-3 text-sm">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3"><dt className="text-slate-600">Open bugs</dt><dd className="font-semibold text-slate-900">{metrics.openBugs}</dd></div>
              <div className="flex items-center justify-between border-b border-slate-100 pb-3"><dt className="text-slate-600">Still in testing</dt><dd className="font-semibold text-slate-900">{metrics.statusCounts.TESTING}</dd></div>
              <div className="flex items-center justify-between border-b border-slate-100 pb-3"><dt className="text-slate-600">Still in code review</dt><dd className="font-semibold text-slate-900">{metrics.statusCounts.CODE_REVIEW}</dd></div>
              <div className="flex items-center justify-between border-b border-slate-100 pb-3"><dt className="text-slate-600">Remaining story points</dt><dd className="font-semibold text-slate-900">{metrics.remainingStoryPoints}</dd></div>
              <div className="flex items-center justify-between"><dt className="text-slate-600">Overdue open issues</dt><dd className="font-semibold text-slate-900">{metrics.overdueIssues}</dd></div>
            </dl>
          </section>
        </div>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-slate-950">Status distribution</h2>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
            {trackedStatuses.map((status) => <div key={status} className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-medium text-slate-500">{statusLabels[status]}</p><p className="mt-1 text-xl font-semibold text-slate-900">{metrics.statusCounts[status]}</p></div>)}
          </div>
        </section>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center gap-2 border-b border-slate-200 p-5"><CalendarDays className="size-5 text-sky-700" /><div><h2 className="font-semibold text-slate-950">Sprint issues</h2><p className="text-sm text-slate-500">Issues assigned to {selectedSprint.name}</p></div></div>
          {!sprintIssues.length ? (
            <p className="p-6 text-center text-sm text-slate-500">No issues assigned to this sprint.</p>
          ) : (
            <div className="overflow-x-auto"><table className="w-full min-w-[42rem] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 font-medium">Issue</th><th className="px-5 py-3 font-medium">Type</th><th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Assignee</th><th className="px-5 py-3 text-right font-medium">Points</th></tr></thead><tbody className="divide-y divide-slate-100">{sprintIssues.map((issue) => <tr key={issue.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelectedIssueKey(issue.issue_key)}><td className="px-5 py-3"><p className="font-mono text-xs text-slate-500">{issue.issue_key}</p><p className="mt-1 font-medium text-slate-800">{issue.title}</p></td><td className="px-5 py-3 text-xs font-medium text-slate-600">{issue.issue_type.toLowerCase()}</td><td className="px-5 py-3"><StatusBadge status={issue.status} /></td><td className="px-5 py-3 text-slate-600">{issue.assignee?.name ?? "Unassigned"}</td><td className="px-5 py-3 text-right font-medium text-slate-700">{issue.story_points ?? "-"}</td></tr>)}</tbody></table></div>
          )}
        </section>
      </section>

      <IssueDetailsDrawer issueKey={selectedIssueKey} onClose={() => setSelectedIssueKey(null)} />
    </>
  );
}
