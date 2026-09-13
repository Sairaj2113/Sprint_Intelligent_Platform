import { Clock3, RotateCcw, TestTube2, Truck } from "lucide-react";

import { StatusBadge } from "./status-badge";
import type {
  AggregateDurationMetrics,
  BugMetrics,
  IssueMetrics,
  IssueWorkflowEvidence,
  StatusDistribution,
  StoryPointMetrics,
  WorkflowEvidenceSummary,
} from "../types/api";

type KpiData = {
  issue_metrics: IssueMetrics;
  story_point_metrics: StoryPointMetrics;
  bug_metrics: BugMetrics;
  status_distribution: StatusDistribution;
  duration_metrics: AggregateDurationMetrics;
};

const stageLabels: Record<string, string> = {
  TODO: "To Do",
  DEVELOPMENT: "Development",
  REVIEW: "Review",
  TESTING: "Testing",
  DONE_NOT_DEPLOYED: "Done, not deployed",
  DEPLOYED: "Deployment evidence",
};

export function formatPercentage(value: number) {
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

export function formatHours(value: number | null) {
  if (value === null) return "N/A";
  return `${Number.isInteger(value) ? value : value.toFixed(1)} h`;
}

export function KpiCards({ kpis, title = "KPI summary" }: { kpis: KpiData; title?: string }) {
  const cards = [
    ["Issue completion", `${kpis.issue_metrics.completed_issues} / ${kpis.issue_metrics.total_issues}`, formatPercentage(kpis.issue_metrics.issue_completion_percentage)],
    ["Story point completion", `${kpis.story_point_metrics.completed_story_points} / ${kpis.story_point_metrics.total_story_points}`, formatPercentage(kpis.story_point_metrics.story_point_completion_percentage)],
    ["Open issues", kpis.issue_metrics.open_issues, "Not in Done status"],
    ["Resolved bugs", kpis.bug_metrics.resolved_bugs, `${kpis.bug_metrics.open_bugs} open bugs`],
  ];
  return <section><h2 className="text-lg font-semibold text-slate-950">{title}</h2><div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label, value, detail]) => <article key={String(label)} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p><p className="mt-1 text-xs text-slate-500">{detail}</p></article>)}</div></section>;
}

export function DurationCards({ durations }: { durations: AggregateDurationMetrics }) {
  const cards = [["Avg cycle time", durations.average_cycle_time_hours], ["Avg development time", durations.average_development_time_hours], ["Avg review time", durations.average_review_time_hours], ["Avg testing time", durations.average_testing_time_hours]];
  return <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center gap-2"><Clock3 className="size-5 text-sky-700" /><div><h2 className="font-semibold text-slate-950">Delivery timing</h2><p className="text-sm text-slate-500">Available history-derived durations</p></div></div><div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label, value]) => <div key={String(label)} className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-xl font-semibold text-slate-900">{formatHours(value as number | null)}</p></div>)}</div></section>;
}

export function WorkflowSummary({ summary }: { summary: WorkflowEvidenceSummary }) {
  const stages = [["TODO", summary.issues_in_todo], ["DEVELOPMENT", summary.issues_in_development], ["REVIEW", summary.issues_in_review], ["TESTING", summary.issues_in_testing], ["DONE_NOT_DEPLOYED", summary.issues_done_not_deployed], ["DEPLOYED", summary.issues_deployed]];
  return <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-semibold text-slate-950">Workflow evidence</h2><div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-6">{stages.map(([stage, count]) => <div key={String(stage)} className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">{stageLabels[String(stage)]}</p><p className="mt-1 text-xl font-semibold text-slate-900">{count}</p></div>)}</div><div className="mt-5 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-5"><p><RotateCcw className="mr-1 inline size-4 text-slate-500" />Reopened: <strong>{summary.reopened_issues}</strong></p><p>Reaching testing: <strong>{summary.issues_reaching_testing}</strong></p><p><TestTube2 className="mr-1 inline size-4 text-slate-500" />Test evidence: <strong>{summary.issues_with_test_evidence}</strong></p><p>Failed-test evidence: <strong>{summary.issues_with_failed_test_evidence}</strong></p><p><Truck className="mr-1 inline size-4 text-slate-500" />Deployment evidence: <strong>{summary.issues_with_deployment_evidence}</strong></p></div></section>;
}

export function WorkflowEvidenceTable({ issues, onSelectIssue }: { issues: IssueWorkflowEvidence[]; onSelectIssue?: (issueKey: string) => void }) {
  return <section className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-200 p-5"><h2 className="font-semibold text-slate-950">Workflow evidence details</h2><p className="text-sm text-slate-500">First {Math.min(issues.length, 8)} documented work items</p></div>{issues.length ? <div className="overflow-x-auto"><table className="w-full min-w-[54rem] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Issue</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Delivery stage</th><th className="px-5 py-3 text-right">Transitions</th><th className="px-5 py-3 text-right">Reopens</th><th className="px-5 py-3 text-right">Tests</th><th className="px-5 py-3 text-right">Failed tests</th><th className="px-5 py-3 text-right">Deployments</th><th className="px-5 py-3 text-right">Cycle time</th></tr></thead><tbody className="divide-y divide-slate-100">{issues.slice(0, 8).map((issue) => <tr key={issue.issue_id} className={onSelectIssue ? "cursor-pointer hover:bg-slate-50" : ""} onClick={() => onSelectIssue?.(issue.issue_key)}><td className="px-5 py-3"><p className="font-mono text-xs text-slate-500">{issue.issue_key}</p><p className="font-medium text-slate-800">{issue.title}</p></td><td className="px-5 py-3"><StatusBadge status={issue.status} /></td><td className="px-5 py-3 text-slate-600">{stageLabels[issue.delivery_stage]}</td><td className="px-5 py-3 text-right">{issue.transition_count}</td><td className="px-5 py-3 text-right">{issue.reopen_count}</td><td className="px-5 py-3 text-right">{issue.test_result_count}</td><td className="px-5 py-3 text-right">{issue.failed_test_count}</td><td className="px-5 py-3 text-right">{issue.deployment_count}</td><td className="px-5 py-3 text-right">{formatHours(issue.cycle_time_hours)}</td></tr>)}</tbody></table></div> : <p className="p-6 text-center text-sm text-slate-500">No workflow evidence is available for this scope.</p>}</section>;
}
