import { ArrowLeft, ClipboardList } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/async-state";
import { EmployeePerformanceReportView } from "../components/employee-performance-report";
import { useEmployeePerformance, useSprintEmployeePerformance } from "../hooks/use-evidence";
import { useProject, useProjectMembers, useProjectSprints } from "../hooks/use-projects";

type ReportScope = "PROJECT" | "SPRINT";

export function EmployeePerformancePage() {
  const { projectKey, employeeId } = useParams();
  const [scope, setScope] = useState<ReportScope>("PROJECT");
  const [selectedSprintId, setSelectedSprintId] = useState("");
  const projectQuery = useProject(projectKey);
  const membersQuery = useProjectMembers(projectKey);
  const sprintsQuery = useProjectSprints(projectKey);
  const member = membersQuery.data?.find((item) => item.employee.id === employeeId)?.employee;
  const activeEmployeeId = member ? employeeId : undefined;
  const projectReportQuery = useEmployeePerformance(
    scope === "PROJECT" ? projectKey : undefined,
    scope === "PROJECT" ? activeEmployeeId : undefined,
  );
  const sprintReportQuery = useSprintEmployeePerformance(
    scope === "SPRINT" ? projectKey : undefined,
    scope === "SPRINT" && selectedSprintId ? selectedSprintId : undefined,
    scope === "SPRINT" ? activeEmployeeId : undefined,
  );

  useEffect(() => {
    if (!selectedSprintId && sprintsQuery.data?.[0]) {
      setSelectedSprintId(sprintsQuery.data[0].id);
    }
  }, [selectedSprintId, sprintsQuery.data]);

  if (projectQuery.isPending || membersQuery.isPending) {
    return <LoadingState title="Loading employee performance report" />;
  }
  if (projectQuery.isError || !projectQuery.data) {
    return <ErrorState title="Project performance report could not be loaded" description="The project may not exist, or the backend service is unavailable." />;
  }
  if (membersQuery.isError) {
    return <ErrorState title="Project members could not be loaded" description="The employee report cannot be scoped safely until project membership is available." />;
  }
  if (!member) {
    return <ErrorState title="Employee performance report is unavailable" description="This employee is not a recorded member of this project." />;
  }

  const project = projectQuery.data;
  const reportQuery = scope === "PROJECT" ? projectReportQuery : sprintReportQuery;
  const tabClassName = ({ isActive }: { isActive: boolean }) => `inline-flex items-center border-b-2 px-1 py-3 text-sm font-medium transition ${isActive ? "border-sky-600 text-sky-700" : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"}`;
  const hasSprints = Boolean(sprintsQuery.data?.length);

  return (
    <section className="w-full">
      <Link to={`/projects/${project.project_key}`} className="inline-flex items-center gap-2 text-sm font-medium text-sky-700 hover:text-sky-900">
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to project workspace
      </Link>
      <header className="mt-5">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">Employee report / {project.project_key}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{member.name}</h1>
        <p className="mt-2 text-sm text-slate-600">{member.employee_code}{member.role ? ` · ${member.role}` : ""}{member.department ? ` · ${member.department}` : ""}</p>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">A deterministic report of recorded project evidence. It is not a score, ranking, or performance judgment.</p>
      </header>

      <nav className="mt-7 flex gap-5 overflow-x-auto border-b border-slate-200" aria-label="Project navigation">
        <NavLink end to={`/projects/${project.project_key}`} className={tabClassName}>Overview</NavLink>
        <NavLink to={`/projects/${project.project_key}/board`} className={tabClassName}>Board</NavLink>
        <NavLink to={`/projects/${project.project_key}/sprints`} className={tabClassName}>Sprints</NavLink>
        <NavLink to={`/projects/${project.project_key}/intelligence`} className={tabClassName}>AI Intelligence</NavLink>
        <NavLink to={`/projects/${project.project_key}/reports`} className={tabClassName}>Reports</NavLink>
      </nav>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="report-scope-heading">
        <div className="flex items-start gap-3">
          <ClipboardList className="mt-0.5 size-5 shrink-0 text-sky-700" aria-hidden="true" />
          <div><h2 id="report-scope-heading" className="font-semibold text-slate-950">Report scope</h2><p className="mt-1 text-sm leading-6 text-slate-500">Choose the recorded project scope or one recorded sprint. Only the selected report is requested.</p></div>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="grid gap-1.5 text-sm font-medium text-slate-700" htmlFor="performance-scope">Scope
            <select id="performance-scope" value={scope} onChange={(event) => setScope(event.target.value as ReportScope)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-sky-600 focus:ring-2 focus:ring-sky-100"><option value="PROJECT">Project</option><option value="SPRINT" disabled={!hasSprints}>Sprint</option></select>
          </label>
          {scope === "SPRINT" ? <label className="grid gap-1.5 text-sm font-medium text-slate-700" htmlFor="performance-sprint">Sprint
            <select id="performance-sprint" value={selectedSprintId} onChange={(event) => setSelectedSprintId(event.target.value)} disabled={sprintsQuery.isPending || !hasSprints} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none disabled:cursor-not-allowed disabled:bg-slate-100 focus:border-sky-600 focus:ring-2 focus:ring-sky-100">{sprintsQuery.data?.map((sprint) => <option key={sprint.id} value={sprint.id}>{sprint.name} ({sprint.status.toLowerCase()})</option>)}</select>
          </label> : null}
        </div>
        {sprintsQuery.isError ? <p className="mt-3 text-sm text-amber-800">Sprint options are currently unavailable. The project report remains available.</p> : null}
      </section>

      {scope === "SPRINT" && !hasSprints && !sprintsQuery.isPending ? <div className="mt-6"><ErrorState title="Sprint scope is unavailable" description="This project has no recorded sprints to select." /></div> : null}
      {scope === "SPRINT" && hasSprints && !selectedSprintId ? <div className="mt-6"><LoadingState title="Preparing sprint report" /></div> : null}
      {reportQuery.isPending ? <div className="mt-6"><LoadingState title="Loading recorded employee evidence" /></div> : null}
      {reportQuery.isError || (!reportQuery.isPending && !reportQuery.data && !(scope === "SPRINT" && !selectedSprintId)) ? <div className="mt-6 space-y-3"><ErrorState title="Employee performance report could not be loaded" description="The report could not be retrieved. Your selected scope has not been changed." /><button type="button" onClick={() => void reportQuery.refetch()} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2">Try again</button></div> : null}
      {reportQuery.data ? <><div className="mt-6 rounded-lg border border-sky-100 bg-sky-50 px-4 py-3 text-sm text-sky-950"><span className="font-semibold">{reportQuery.data.scope.kind === "SPRINT" ? `Sprint: ${reportQuery.data.scope.sprint_name ?? "Recorded sprint"}` : "Project scope"}</span><span className="ml-2 text-sky-800">{reportQuery.data.scope.definition}</span></div><EmployeePerformanceReportView report={reportQuery.data} /></> : null}
    </section>
  );
}
