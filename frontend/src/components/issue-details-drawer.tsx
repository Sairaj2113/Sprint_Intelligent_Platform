import { CircleUserRound, TestTube2, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { ErrorState, LoadingState } from "./async-state";
import { StatusBadge } from "./status-badge";
import {
  useIssue,
  useIssueComments,
  useIssueDeployments,
  useIssueHistory,
  useIssueTests,
} from "../hooks/use-issue-details";
import type { Issue, IssueType } from "../types/api";

type DrawerTab = "overview" | "history" | "comments" | "tests" | "deployments";

type IssueDetailsDrawerProps = {
  issueKey: string | null;
  onClose: () => void;
};

const tabs: Array<{ id: DrawerTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "history", label: "History" },
  { id: "comments", label: "Comments" },
  { id: "tests", label: "Tests" },
  { id: "deployments", label: "Deployments" },
];

const issueTypeStyles: Record<IssueType, string> = {
  EPIC: "bg-violet-50 text-violet-700 ring-violet-200",
  STORY: "bg-sky-50 text-sky-700 ring-sky-200",
  TASK: "bg-slate-100 text-slate-700 ring-slate-200",
  BUG: "bg-rose-50 text-rose-700 ring-rose-200",
  SUBTASK: "bg-amber-50 text-amber-700 ring-amber-200",
};

function formatLabel(value: string) {
  return value.replace(/_/g, " ").toLowerCase();
}

function formatDate(value: string | null) {
  if (!value) return "Not set";
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

function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-slate-100 pt-5">
      <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{title}</h3>
      <div className="mt-2 text-sm leading-6 text-slate-700">{children}</div>
    </section>
  );
}

function OverviewTab({ issue }: { issue: Issue }) {
  return (
    <div className="space-y-5 p-5">
      <div className="grid grid-cols-2 gap-x-4 gap-y-5 rounded-lg bg-slate-50 p-4 text-sm sm:grid-cols-3">
        <div><p className="text-xs text-slate-500">Assignee</p><p className="mt-1 font-medium text-slate-800">{issue.assignee?.name ?? "Unassigned"}</p></div>
        <div><p className="text-xs text-slate-500">Reporter</p><p className="mt-1 font-medium text-slate-800">{issue.reporter?.name ?? "Not set"}</p></div>
        <div><p className="text-xs text-slate-500">Sprint</p><p className="mt-1 font-medium text-slate-800">{issue.sprint?.name ?? "Unassigned"}</p></div>
        <div><p className="text-xs text-slate-500">Parent issue</p><p className="mt-1 font-mono text-xs font-medium text-slate-800">{issue.parent_issue?.issue_key ?? "None"}</p></div>
        <div><p className="text-xs text-slate-500">Start date</p><p className="mt-1 font-medium text-slate-800">{formatDate(issue.start_date)}</p></div>
        <div><p className="text-xs text-slate-500">Due date</p><p className="mt-1 font-medium text-slate-800">{formatDate(issue.due_date)}</p></div>
      </div>
      <DetailSection title="Description">{issue.description ?? "No description recorded."}</DetailSection>
      <DetailSection title="Acceptance criteria">{issue.acceptance_criteria ?? "No acceptance criteria recorded."}</DetailSection>
      <DetailSection title="Technical notes">{issue.technical_notes ?? "No technical notes recorded."}</DetailSection>
    </div>
  );
}

export function IssueDetailsDrawer({ issueKey, onClose }: IssueDetailsDrawerProps) {
  const [activeTab, setActiveTab] = useState<DrawerTab>("overview");
  const isOpen = Boolean(issueKey);
  const issueQuery = useIssue(issueKey, isOpen);
  const historyQuery = useIssueHistory(issueKey, isOpen && activeTab === "history");
  const commentsQuery = useIssueComments(issueKey, isOpen && activeTab === "comments");
  const testsQuery = useIssueTests(issueKey, isOpen && activeTab === "tests");
  const deploymentsQuery = useIssueDeployments(
    issueKey,
    isOpen && activeTab === "deployments",
  );

  useEffect(() => {
    setActiveTab("overview");
  }, [issueKey]);

  if (!issueKey) return null;

  const renderTabContent = () => {
    if (!issueQuery.data) return null;

    if (activeTab === "overview") return <OverviewTab issue={issueQuery.data} />;
    if (activeTab === "history") {
      if (historyQuery.isPending) return <div className="p-5"><LoadingState title="Loading issue history" /></div>;
      if (historyQuery.isError) return <div className="p-5"><ErrorState title="History could not be loaded" /></div>;
      if (!historyQuery.data?.length) return <p className="p-5 text-sm text-slate-500">No history recorded.</p>;
      return <div className="divide-y divide-slate-100">{historyQuery.data.map((history) => <article key={history.id} className="p-5"><p className="font-semibold text-slate-800">{history.old_status ? formatLabel(history.old_status) : "Created"} <span className="text-slate-400">→</span> {formatLabel(history.new_status)}</p><p className="mt-1 text-sm text-slate-600">Changed by {history.changed_by_employee?.name ?? "Unknown employee"}</p><p className="mt-1 text-xs text-slate-500">{formatTimestamp(history.changed_at)}</p>{history.notes && <p className="mt-3 rounded bg-slate-50 p-3 text-sm leading-5 text-slate-700">{history.notes}</p>}</article>)}</div>;
    }
    if (activeTab === "comments") {
      if (commentsQuery.isPending) return <div className="p-5"><LoadingState title="Loading comments" /></div>;
      if (commentsQuery.isError) return <div className="p-5"><ErrorState title="Comments could not be loaded" /></div>;
      if (!commentsQuery.data?.length) return <p className="p-5 text-sm text-slate-500">No comments recorded.</p>;
      return <div className="divide-y divide-slate-100">{commentsQuery.data.map((comment) => <article key={comment.id} className="p-5"><div className="flex items-center gap-2"><CircleUserRound className="size-4 text-slate-400" /><p className="font-semibold text-slate-800">{comment.employee?.name ?? "Unknown employee"}</p></div><p className="mt-1 text-xs text-slate-500">{formatTimestamp(comment.created_at)}</p><p className="mt-3 text-sm leading-6 text-slate-700">{comment.content}</p></article>)}</div>;
    }
    if (activeTab === "tests") {
      if (testsQuery.isPending) return <div className="p-5"><LoadingState title="Loading test evidence" /></div>;
      if (testsQuery.isError) return <div className="p-5"><ErrorState title="Test evidence could not be loaded" /></div>;
      if (!testsQuery.data?.length) return <p className="p-5 text-sm text-slate-500">No test evidence recorded.</p>;
      return <div className="space-y-3 p-5">{testsQuery.data.map((test) => <article key={test.id} className="rounded-lg border border-slate-200 p-4"><div className="flex items-center justify-between gap-3"><p className="font-semibold text-slate-800">{formatLabel(test.testing_status)}</p><TestTube2 className="size-4 text-sky-700" /></div><dl className="mt-3 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-xs text-slate-500">Test cases total</dt><dd className="font-medium text-slate-800">{test.test_cases_total ?? "Not recorded"}</dd></div><div><dt className="text-xs text-slate-500">Test cases passed</dt><dd className="font-medium text-slate-800">{test.test_cases_passed ?? "Not recorded"}</dd></div><div><dt className="text-xs text-slate-500">Bugs found</dt><dd className="font-medium text-slate-800">{test.bugs_found ?? "Not recorded"}</dd></div><div><dt className="text-xs text-slate-500">Reopened count</dt><dd className="font-medium text-slate-800">{test.reopened_count ?? "Not recorded"}</dd></div></dl><p className="mt-3 text-xs text-slate-500">Tested by {test.tested_by_employee?.name ?? "Unknown employee"} · {formatTimestamp(test.tested_at)}</p>{test.testing_notes && <p className="mt-3 text-sm leading-5 text-slate-700">{test.testing_notes}</p>}</article>)}</div>;
    }
    if (deploymentsQuery.isPending) return <div className="p-5"><LoadingState title="Loading deployment evidence" /></div>;
    if (deploymentsQuery.isError) return <div className="p-5"><ErrorState title="Deployments could not be loaded" /></div>;
    if (!deploymentsQuery.data?.length) return <p className="p-5 text-sm text-slate-500">No deployment evidence recorded.</p>;
    return <div className="space-y-3 p-5">{deploymentsQuery.data.map((deployment) => <article key={deployment.id} className="rounded-lg border border-slate-200 p-4"><div className="flex items-center justify-between gap-3"><p className="font-semibold text-slate-800">{deployment.environment ?? "Environment not recorded"}</p><span className="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{formatLabel(deployment.deployment_status)}</span></div><p className="mt-2 text-xs text-slate-500">{formatTimestamp(deployment.deployment_date)}</p>{deployment.production_notes && <p className="mt-3 text-sm leading-5 text-slate-700">{deployment.production_notes}</p>}{deployment.production_incidents && <p className="mt-3 rounded bg-amber-50 p-3 text-sm leading-5 text-amber-900">Incidents: {deployment.production_incidents}</p>}</article>)}</div>;
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Issue details">
      <button className="absolute inset-0 bg-slate-950/35" aria-label="Close issue details" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-xl flex-col bg-white shadow-2xl">
        <header className="border-b border-slate-200 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              {issueQuery.isPending && <p className="text-sm text-slate-500">Loading issue details…</p>}
              {issueQuery.isError && <p className="text-sm font-medium text-rose-700">Issue details could not be loaded.</p>}
              {issueQuery.data && <><p className="font-mono text-xs font-semibold text-slate-500">{issueQuery.data.issue_key}</p><h2 className="mt-1 text-lg font-semibold leading-6 text-slate-950">{issueQuery.data.title}</h2><div className="mt-3 flex flex-wrap items-center gap-2"><span className={`rounded px-2 py-1 text-xs font-semibold ring-1 ring-inset ${issueTypeStyles[issueQuery.data.issue_type]}`}>{issueQuery.data.issue_type.toLowerCase()}</span><StatusBadge status={issueQuery.data.status} /><span className="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{issueQuery.data.priority.toLowerCase()} priority</span>{issueQuery.data.story_points !== null && <span className="text-xs font-medium text-slate-600">{issueQuery.data.story_points} points</span>}</div></>}
            </div>
            <button className="grid size-9 shrink-0 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800" aria-label="Close issue details" onClick={onClose}><X className="size-5" /></button>
          </div>
        </header>
        {issueQuery.data && <nav className="flex overflow-x-auto border-b border-slate-200 px-5" aria-label="Issue detail tabs">{tabs.map((tab) => <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`shrink-0 border-b-2 px-3 py-3 text-sm font-medium ${activeTab === tab.id ? "border-sky-600 text-sky-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{tab.label}</button>)}</nav>}
        <div className="min-h-0 flex-1 overflow-y-auto">{issueQuery.isPending && <div className="p-5"><LoadingState title="Loading issue details" /></div>}{issueQuery.isError && <div className="p-5"><ErrorState title="Issue details could not be loaded" /></div>}{issueQuery.data && renderTabContent()}</div>
      </aside>
    </div>
  );
}
