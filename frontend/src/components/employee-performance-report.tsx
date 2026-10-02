import {
  Activity,
  ClipboardCheck,
  FileCheck2,
  Gauge,
  MessageSquareText,
  RotateCcw,
  TestTube2,
  Timer,
  Truck,
} from "lucide-react";

import { formatHours, formatPercentage } from "./evidence-ui";
import type { EmployeePerformanceReport } from "../types/api";

type EmployeePerformanceReportProps = {
  report: EmployeePerformanceReport;
};

type MetricCardProps = {
  label: string;
  value: string | number;
  detail?: string;
};

const statusLabels = [
  ["Backlog", "backlog"],
  ["Selected for Sprint", "selected_for_sprint"],
  ["To Do", "todo"],
  ["In Progress", "in_progress"],
  ["Code Review", "code_review"],
  ["Testing", "testing"],
  ["Ready for Release", "ready_for_release"],
  ["Done", "done"],
] as const;

function MetricCard({ label, value, detail }: MetricCardProps) {
  return (
    <article className="rounded-lg bg-slate-50 p-3">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-950">{value}</p>
      {detail ? <p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p> : null}
    </article>
  );
}

function SectionHeader({ icon: Icon, title, description }: {
  icon: typeof Activity;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <Icon className="mt-0.5 size-5 shrink-0 text-sky-700" aria-hidden="true" />
      <div>
        <h2 className="font-semibold text-slate-950">{title}</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>
      </div>
    </div>
  );
}

function TimingMetric({ label, average, eligible }: {
  label: string;
  average: number | null;
  eligible: number;
}) {
  return (
    <article className="rounded-lg bg-slate-50 p-3">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-950">
        {average === null ? "Not available" : formatHours(average)}
      </p>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        Eligible issues: {eligible}
      </p>
    </article>
  );
}

export function EmployeePerformanceReportView({ report }: EmployeePerformanceReportProps) {
  const { delivery, quality, deployment_evidence: deployments, requirement_connections: requirements } = report;
  const completionRate = delivery.completion_rate_percentage;
  const passRate = quality.test_case_pass_rate_percentage;
  const completionProgress = completionRate === null ? undefined : Math.max(0, Math.min(100, completionRate));

  return (
    <div className="mt-6 space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="delivery-metrics-heading">
        <SectionHeader icon={Gauge} title="Recorded delivery metrics" description="Assignment and completion records for the selected scope; these are not a performance score." />
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Assigned issues" value={delivery.assigned_issue_count} />
          <MetricCard label="Completed issues" value={delivery.completed_issue_count} />
          <MetricCard label="Assigned story-point estimates" value={delivery.assigned_story_points} detail="Recorded estimates, not effort or productivity." />
          <MetricCard label="Completed story-point estimates" value={delivery.completed_story_points} detail="Recorded estimates, not effort or productivity." />
          <MetricCard label="Assigned bugs" value={delivery.assigned_bug_count} />
          <MetricCard label="Resolved bugs" value={delivery.resolved_bug_count} />
          <MetricCard label="Reopened assigned issues" value={delivery.reopened_assigned_issue_count} />
          <MetricCard label="Total recorded reopens" value={delivery.total_reopen_count} />
        </div>
        <div className="mt-5 rounded-lg border border-slate-200 p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="text-sm font-semibold text-slate-900">Recorded completion ratio</h3>
            <span className="text-sm font-semibold text-slate-800">
              {completionRate === null ? "Not available" : formatPercentage(completionRate)}
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {delivery.completed_issue_count} completed of {delivery.completion_rate_eligible_issue_count} eligible assigned issues.
          </p>
          {completionProgress !== undefined ? (
            <progress className="mt-3 h-2 w-full accent-sky-600" value={completionProgress} max={100} aria-label="Recorded completion ratio" />
          ) : null}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="status-distribution-heading">
        <SectionHeader icon={Activity} title="Issue status distribution" description="Recorded status counts for all currently assigned issues in the selected scope." />
        <div className="mt-5 grid gap-3 grid-cols-2 sm:grid-cols-4 xl:grid-cols-8">
          {statusLabels.map(([label, key]) => <MetricCard key={key} label={label} value={delivery.status_distribution[key]} />)}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="quality-evidence-heading">
        <SectionHeader icon={TestTube2} title="Linked test evidence" description="Test records linked to assigned issues; they do not establish that this employee performed testing." />
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Completed assigned issues" value={quality.completed_assigned_issue_count} />
          <MetricCard label="Completed with test evidence" value={quality.completed_issues_with_test_evidence} />
          <MetricCard label="Completed without test evidence" value={quality.completed_issues_without_test_evidence} />
          <MetricCard label="Linked test-result records" value={quality.linked_test_result_count} />
          <MetricCard label="Valid test-case records" value={quality.test_records_with_valid_case_counts} />
          <MetricCard label="Test cases total" value={quality.test_cases_total} />
          <MetricCard label="Test cases passed" value={quality.test_cases_passed} />
          <MetricCard label="Test cases failed" value={quality.test_cases_failed} />
        </div>
        <div className="mt-5 rounded-lg border border-slate-200 p-4">
          <p className="text-sm font-semibold text-slate-900">Recorded test-case pass rate</p>
          <p className="mt-1 text-2xl font-semibold text-slate-950">{passRate === null ? "Not available" : formatPercentage(passRate)}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">Eligibility: {quality.test_case_pass_rate_eligible_record_count} valid test-case record{quality.test_case_pass_rate_eligible_record_count === 1 ? "" : "s"}.</p>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="deployment-evidence-heading">
        <SectionHeader icon={Truck} title="Deployment evidence linked to assigned issues" description="Recorded deployment evidence; it does not establish that this employee performed a deployment." />
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Assigned issues with deployment evidence" value={deployments.assigned_issues_with_deployment_evidence} />
          <MetricCard label="Deployment records" value={deployments.deployment_record_count} />
          <MetricCard label="Not deployed" value={deployments.not_deployed_count} />
          <MetricCard label="Staging" value={deployments.staging_count} />
          <MetricCard label="Production" value={deployments.production_count} />
          <MetricCard label="Failed" value={deployments.failed_count} />
          <MetricCard label="Records without environment" value={deployments.deployments_without_recorded_environment} />
        </div>
        <div className="mt-5 rounded-lg border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-900">Recorded environments</h3>
          {Object.keys(deployments.environment_counts).length ? <div className="mt-3 flex flex-wrap gap-2">{Object.entries(deployments.environment_counts).map(([environment, count]) => <span key={environment} className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-sm text-slate-700">{environment}: {count}</span>)}</div> : <p className="mt-2 text-sm text-slate-500">No deployment environments are recorded for this scope.</p>}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="requirement-connections-heading">
        <SectionHeader icon={FileCheck2} title="Explicit implemented requirement connections" description="Only explicitly persisted IMPLEMENTED_BY_ISSUE connections are shown; they do not establish requirement ownership or complete implementation." />
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <MetricCard label="Explicit connection count" value={requirements.explicit_implemented_requirement_link_count} />
        </div>
        {requirements.explicit_implemented_requirement_keys.length ? <div className="mt-5 flex flex-wrap gap-2">{requirements.explicit_implemented_requirement_keys.map((key) => <span key={key} className="rounded-md border border-sky-200 bg-sky-50 px-2.5 py-1 font-mono text-xs font-medium text-sky-800">{key}</span>)}</div> : <p className="mt-5 text-sm text-slate-500">No explicit implemented requirement connections are recorded for this scope.</p>}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="documented-activity-heading">
        <SectionHeader icon={MessageSquareText} title="Documented activity" description="Authored comments are documented activity only and do not establish issue ownership." />
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <MetricCard label="Comments authored" value={report.documented_activity.authored_comment_count} />
          <MetricCard label="Distinct issues commented on" value={report.documented_activity.issues_commented_on_count} />
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="lifecycle-timing-heading">
        <SectionHeader icon={Timer} title="Lifecycle timing" description="Lifecycle duration represents recorded issue lifecycle time and does not represent time personally worked by the employee." />
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <TimingMetric label="Average cycle time" average={report.lifecycle_timing.average_cycle_time_hours} eligible={report.lifecycle_timing.cycle_time_eligible_issue_count} />
          <TimingMetric label="Average development time" average={report.lifecycle_timing.average_development_time_hours} eligible={report.lifecycle_timing.development_time_eligible_issue_count} />
          <TimingMetric label="Average review time" average={report.lifecycle_timing.average_review_time_hours} eligible={report.lifecycle_timing.review_time_eligible_issue_count} />
          <TimingMetric label="Average testing time" average={report.lifecycle_timing.average_testing_time_hours} eligible={report.lifecycle_timing.testing_time_eligible_issue_count} />
        </div>
      </section>

      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-sm sm:p-6" aria-labelledby="performance-limitations-heading">
        <div className="flex items-start gap-3"><ClipboardCheck className="mt-0.5 size-5 shrink-0 text-amber-700" aria-hidden="true" /><div><h2 id="performance-limitations-heading" className="font-semibold text-slate-950">Evidence and interpretation notes</h2><p className="mt-1 text-sm leading-6 text-slate-700">These backend-provided notes define the factual limits of this deterministic report.</p></div></div>
        <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-700">{report.limitations.map((limitation, index) => <li key={`${limitation}-${index}`}>{limitation}</li>)}</ul>
      </section>
    </div>
  );
}
